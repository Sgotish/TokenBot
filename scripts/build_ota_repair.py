"""Build public one-time update ZIP; no client key or customer profile included."""
import argparse,base64,json,hashlib,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser();a.add_argument('manifest',type=Path);a.add_argument('asset',type=Path);a.add_argument('output',type=Path);args=a.parse_args()
# Cryptographic verification is also performed by the installer before applying.
import subprocess
subprocess.run(['node','-e',"require('./integrations/windows-codex/native-menu/ota-client.cjs').verify(require('fs').readFileSync(process.argv[1]))",str(args.manifest.resolve())],cwd=root,check=True)
r=json.loads(base64.b64decode(json.loads(args.manifest.read_bytes())['payload']))
asset=r['assets'][0]
assert hashlib.sha256(args.asset.read_bytes()).hexdigest()==asset['sha256']
readme=f'''TokenBots Codex 更新包 {r['version']}

只用于已经安装的 TokenBots Windows 定制版；保留原有 Key、项目和会话。
1. 保存任务，并完全退出 TokenBots Codex。
2. 把本 ZIP 完整解压。双击“更新现有客户端.cmd”。
3. 看到 Update complete 后，从原来的桌面 TokenBots Codex 快捷方式打开。
4. 左下角账号菜单 → 检查更新。

已经检查过，是最新版本：显示当前版本、上次检查、Last update（上次安装时间）。
发现新版本：点击“更新”，下载并验签后先保存任务，完全退出再用原快捷方式打开。
网络/校验失败会明确提示；不会误报最新，也不会强制结束任务。

此包不含客户 API Key，不需要重新注册或重新安装官方程序。
不要在 ZIP 预览中直接运行，不要关闭杀毒软件。报错时保留提示文字联系我们。
检查的是 TokenBots 定制版本；官方基础客户端升级需要兼容适配后通过本渠道发布。
'''
cmd='''@echo off
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0update-existing.ps1"
if errorlevel 1 goto failed
echo Update complete. Open TokenBots Codex using your desktop shortcut.
pause
exit /b 0
:failed
echo Update stopped. Save the error message and contact TokenBots.
pause
exit /b 1
'''
args.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED) as z:
    for name in ['enable-ota.ps1','ota-client.cjs','update-existing.ps1']:
        z.write(root/'integrations/windows-codex/native-menu'/name,name)
    z.writestr('ota-seed.json',args.manifest.read_bytes())
    z.writestr('browser-asset.json',json.dumps(asset))
    z.write(args.asset,'browser-tools.zip')
    z.writestr('使用说明.txt',readme.encode('utf-8-sig'))
    for name in ['更新现有客户端.cmd','enable-updates.cmd']:
        z.writestr(name,cmd.replace('\n','\r\n').encode('ascii'))
print(json.dumps({'file':str(args.output),'version':r['version'],'bytes':args.output.stat().st_size,'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))
