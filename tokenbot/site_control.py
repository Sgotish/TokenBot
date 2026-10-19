"""Authenticated website control plane. No account credentials leave this service."""
import asyncio
import base64
import fcntl
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time
import zipfile

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from .model_catalog import discovery
from .partner_portal import PoolState, accepts_digest


class ControlError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


class SiteControl:
    def __init__(self, root, secret, provision=None):
        self.root, self.secret = Path(root), secret
        self.provision = provision or self._provision
        self.private = self.root/'private'

    def _provision(self, cid):
        r = subprocess.run([str(self.root/'venv/bin/python'), str(self.root/'scripts/provision_cloud_client.py'),
            cid, '--label', 'TokenBots 网站测试', '--upstream-cidr', '172.18.0.1/32'],
            cwd=self.root, capture_output=True, timeout=80)
        if r.returncode:
            raise ControlError('接入开通未完成，请稍后重试。', 503)

    def registry(self):
        main = json.loads((self.private/'partner.json').read_text())
        path = Path(main['clients_path'])
        return main, path, json.loads(path.read_text())

    def save(self, path, data):
        st = path.stat()
        temp = path.with_suffix('.site-tmp')
        with temp.open('w') as f:
            os.chmod(temp, st.st_mode & 0o777)
            os.chown(temp, st.st_uid, st.st_gid)
            json.dump(data, f, ensure_ascii=False)
            f.flush(); os.fsync(f.fileno())
        temp.replace(path)

    def public(self, cfg):
        state = PoolState(cfg).status()
        return {**state, 'enabled': cfg.get('enabled', True), 'pricing_mode':'test',
            'base_url':'https://pilot.tokenbots.top/v1', 'models':discovery()['data'],
            'keys':[{k:v for k,v in item.items() if k != 'digest'} | {'id':kid}
                    for kid,item in cfg.get('aliases',{}).items()]}

    def run(self, action, data):
        uid = data.get('uid', '')
        if not re.fullmatch(r'[0-9a-f]{32}', uid):
            raise ControlError('账户标识无效。')
        cid = 'web-'+uid
        # Serializes read-modify-write and first provisioning across requests/processes.
        with (self.private/'site-control.lock').open('a') as lock, (self.private/'provision.lock').open('a') as provision_lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            fcntl.flock(provision_lock, fcntl.LOCK_EX)
            main, path, registry = self.registry()
            if action == 'admin-summary':
                return {'items':[{'client_id':k, **self.public(v)} for k,v in registry['clients'].items()
                                 if k.startswith('web-')]}
            cfg = registry['clients'].get(cid)
            if not cfg and action == 'create-key':
                if sum(k.startswith('web-') for k in registry['clients']) >= 20:
                    raise ControlError('本轮测试名额已满，请联系管理员。', 409)
                fcntl.flock(provision_lock, fcntl.LOCK_UN)
                try:
                    self.provision(cid)
                finally:
                    fcntl.flock(provision_lock, fcntl.LOCK_EX)
                main, path, registry = self.registry()
                cfg = registry['clients'].get(cid)
            if not cfg:
                if action == 'status':
                    return {'enabled':True,'configured':False,'keys':[], 'models':discovery()['data'],
                            'base_url':'https://pilot.tokenbots.top/v1','pricing_mode':'test',
                            'accounts':[], 'records':[], 'totals':{}}
                raise ControlError('尚未开通测试接入。', 404)
            if action == 'set-enabled':
                if type(data.get('enabled')) is not bool:
                    raise ControlError('状态无效。')
                cfg['enabled'] = data['enabled']; self.save(path, registry)
                return {'ok':True}
            if cfg.get('enabled',True) is not True:
                raise ControlError('测试接入已停用。', 403)
            if action == 'status':
                return {'configured':True, **self.public(cfg)}
            aliases = cfg.setdefault('aliases', {})
            if action == 'create-key':
                kid, label = data.get('request_id',''), data.get('label','')
                if not re.fullmatch(r'[0-9a-f]{32}', kid) or not isinstance(label,str) or not 1<=len(label)<=60 or any(ord(c)<32 for c in label):
                    raise ControlError('请填写有效的密钥名称。')
                value = 'sk-tb-'+hmac.new(self.secret.encode(), ('key:'+uid+':'+kid).encode(), hashlib.sha256).hexdigest()
                if kid not in aliases:
                    if len(aliases)>=30 or sum(x['enabled'] for x in aliases.values())>=10:
                        raise ControlError('测试密钥数量已达上限，请先停用不需要的密钥。',409)
                    aliases[kid] = {'digest':hashlib.sha256(value.encode()).hexdigest(), 'label':label,
                                    'suffix':value[-6:],'enabled':True,'created':int(time.time())}
                    self.save(path,registry)
                elif not aliases[kid]['enabled']:
                    raise ControlError('此创建请求对应的密钥已停用，请重新创建。',409)
                return {'id':kid,'api_key':value,'base_url':'https://pilot.tokenbots.top/v1'}
            if action == 'revoke-key':
                kid=data.get('id')
                if kid not in aliases: raise ControlError('未找到此账户的密钥。',404)
                aliases[kid]['enabled']=False; self.save(path,registry)
                return {'ok':True}
            if action == 'package':
                key=data.get('api_key','')
                if not isinstance(key,str) or not key.startswith('sk-tb-') or not accepts_digest(cfg,hashlib.sha256(key.encode()).hexdigest()):
                    raise ControlError('请提供当前账户的有效密钥。',403)
                return {'zip_base64':base64.b64encode(self.package(cid,key)).decode()}
            raise ControlError('接口不存在。',404)

    def package(self,cid,key):
        output=io.BytesIO()
        access={'key':key,'label':'TokenBots '+cid,'public_origin':'https://pilot.tokenbots.top',
                'base_url':'https://pilot.tokenbots.top/v1'}
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
            def put(name,value,executable=False):
                info=zipfile.ZipInfo('TokenBots/'+name); info.create_system=3
                info.external_attr=(0o100700 if executable else 0o100600)<<16
                z.writestr(info,value)
            put('access.json',json.dumps(access))
            put('tokenbots.cjs',(self.root/'integrations/codex-client/dist/tokenbots.cjs').read_bytes())
            put('THIRD-PARTY-LICENSE.txt',(self.root/'integrations/codex-client/node_modules/smol-toml/LICENSE').read_bytes())
            for target in ('desktop','cli'):
                put('setup-'+target+'.cmd','@echo off\r\ncd /d "%~dp0"\r\nnode tokenbots.cjs setup --target '+target+' --access access.json\r\npause\r\n')
                put('setup-'+target+'.command','#!/bin/sh\ncd -- "$(dirname -- "$0")" || exit 1\nnode ./tokenbots.cjs setup --target '+target+' --access ./access.json\n',True)
            setup=(self.root/'integrations/windows-codex/setup.ps1.template').read_text().replace('__BASE_URL__',access['base_url']).replace('__TEST_KEY__',key).replace('TokenBots Partner Test',access['label'])
            put('setup.ps1',setup.encode('utf-8-sig'))
            for file in (self.root/'integrations/windows-codex/native-menu').iterdir():
                if file.suffix in ('.ps1','.js','.cjs'): put('native-menu/'+file.name,file.read_bytes())
            put('native-menu/native-access.json',json.dumps({'origin':access['public_origin'],'key':key}))
            put('install-native.cmd','@echo off\r\ncd /d "%~dp0"\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File setup.ps1\r\nif errorlevel 1 goto done\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File native-menu\\install.ps1\r\n:done\r\npause\r\n')
            put('README.txt',('TokenBots 专属测试接入包\n\n仅给当前账户使用，包含私密 API Key。不要上传公开仓库或转发其他客户。\n'
                'Windows 原生用量菜单：退出 Codex，完整解压后运行 install-native.cmd，随后从 TokenBots Codex 快捷方式启动。\n'
                'Mac / Linux / Windows CLI：先安装 Node.js 20+ 和官方 Codex；运行对应 setup-desktop 或 setup-cli。Linux 可执行 sh setup-cli.command。\n'
                'WSL 请在 WSL 内单独配置，不与 Windows 共用配置目录。\n'
                '新配置默认 Astra/high，已有有效选择保留。七个模型共用同一把 Key；在 Codex 内选择模型和支持的强度，无需网站选渠道。\n'
                '跨平台回退：node tokenbots.cjs rollback --target cli（桌面配置将 cli 改为 desktop）；自定义目录需另加 --home。Windows 定制副本回退请退出后打开原版应用。\n'
                'Windows 定制副本并非官方发行版；原版保留。Mac/Linux 此包仅配置接入，未添加原生用量菜单。\n'
                '测试期间不收费；上游订阅容量仍有限。需要停用 Key 时在网站操作。\n').encode('utf-8-sig'))
        return output.getvalue()


def create_app(control):
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    slots=asyncio.Semaphore(2)
    @app.post('/internal/site/{action}')
    async def call(action:str,request:Request):
        auth=request.headers.get('authorization','')
        if not hmac.compare_digest(auth,'Bearer '+control.secret):
            return JSONResponse({'error':'Unauthorized'},status_code=401,headers={'Cache-Control':'no-store'})
        if slots.locked(): return JSONResponse({'error':'操作正在处理，请稍后重试。'},status_code=429)
        async with slots:
            try:
                async with asyncio.timeout(5):
                    body=bytearray()
                    async for chunk in request.stream():
                        body.extend(chunk)
                        if len(body)>4096: raise ControlError('请求过大。',413)
                data=json.loads(body)
                if not isinstance(data,dict): raise ControlError('请求无效。')
                result=await run_in_threadpool(control.run,action,data)
                return JSONResponse(result,headers={'Cache-Control':'no-store'})
            except ControlError as exc:
                return JSONResponse({'error':exc.message},status_code=exc.status,headers={'Cache-Control':'no-store'})
            except Exception:
                return JSONResponse({'error':'操作未完成，请稍后重试。'},status_code=503,headers={'Cache-Control':'no-store'})
    return app


def app_factory():
    secret=Path('/opt/tokenbot-pilot/private/site-control.secret').read_text().strip()
    if len(secret)<40: raise ValueError('Missing control secret')
    return create_app(SiteControl('/opt/tokenbot-pilot',secret))
