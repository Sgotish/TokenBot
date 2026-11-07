'use strict';
// Runs in the desktop main process. The renderer never receives a bearer key.
const fs = require('node:fs');
const path = require('node:path');

async function handle(request) {
  const reply = (data, status = 200) => new Response(JSON.stringify(data), {
    status, headers: {'Content-Type': 'application/json', 'Cache-Control': 'no-store'},
  });
  try {
    const url = new URL(request.url);
    const origin = request.headers?.get('origin');
    if (url.protocol !== 'app:' || url.host !== '-' || (origin && origin !== 'app://-')) {
      return reply({error: '来源不匹配'}, 403);
    }
    if (url.pathname === '/tokenbots-native/update' || url.pathname === '/tokenbots-native/update/check' || url.pathname === '/tokenbots-native/update/download') {
      const app=path.dirname(process.resourcesPath);
      if(!fs.existsSync(path.join(app,'.tokenbots-custom-copy')))return reply({error:'无法确认安装位置'},503);
      const updater=path.join(app,'ota-client.cjs');
      const ota=require(updater);
      const dir=path.join(app,'tokenbots-ota'); fs.mkdirSync(dir,{recursive:true});
      if(url.pathname==='/tokenbots-native/update' && request.method==='GET') return reply(ota.state(dir));
      if(request.method!=='POST')return reply({error:'Method not allowed'},405);
      const action=url.pathname.endsWith('/check')?'check':url.pathname.endsWith('/download')?'fetch':null;
      if(!action)return reply({error:'Not found'},404);
      try {
        await new Promise((resolve,reject)=>require('node:child_process').execFile(
          path.join(process.resourcesPath,'cua_node','bin','node.exe'),[updater,action,app],
          {windowsHide:true,timeout:150000,maxBuffer:4096},err=>err?reject(err):resolve()));
        return reply(ota.state(dir));
      } catch { const result=ota.state(dir); return reply({...result,error:result.error||'更新操作未完成，请稍后重试。'},503); }
    }
    const config = JSON.parse(fs.readFileSync(path.join(process.resourcesPath, 'tokenbots-native.json'), 'utf8'));
    const target = new URL(config.origin);
    const localTest = config.testOnlyLocalOrigin === true && target.protocol === 'http:' && target.hostname === '127.0.0.1';
    if ((!localTest && target.protocol !== 'https:') || target.username || target.password || target.pathname !== '/' || target.search || target.hash || !config.key) {
      return reply({error: '用量接入配置无效'}, 503);
    }
    let endpoint, body;
    const method = request.method || 'GET';
    if (url.pathname === '/tokenbots-native/usage' && method === 'GET') {
      endpoint = '/v1/usage';
    } else if (url.pathname === '/tokenbots-native/pool' && method === 'POST') {
      const raw = await request.text();
      if (raw.length > 128) return reply({error: '输入过长'}, 413);
      const value = JSON.parse(raw);
      if (!['auto', 'plus', 'pro'].includes(value.pool)) return reply({error: '无效号池'}, 400);
      endpoint = '/portal/api/pool';
      body = JSON.stringify({pool: value.pool});
    } else return reply({error: 'Not found'}, 404);
    const upstream = await fetch(new URL(endpoint, target), {
      method, redirect: 'error', signal: AbortSignal.timeout(10000),
      headers: {Authorization: 'Bearer ' + config.key, Origin: target.origin, 'Content-Type': 'application/json'}, body,
    });
    if (!upstream.ok) return reply({error: upstream.status === 409 ? '仍有调用进行中，请结束任务后再切换' : '用量服务暂不可用，请稍后重试'}, upstream.status);
    return reply(await upstream.json());
  } catch {
    return reply({error: '无法读取用量，请检查网络或接入配置'}, 503);
  }
}
module.exports = {handle};
