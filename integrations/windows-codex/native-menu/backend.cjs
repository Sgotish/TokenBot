'use strict';
// Runs in the desktop main process. The renderer never receives a bearer key.
const fs = require('node:fs');
const path = require('node:path');

function initialize() {
  const {app} = require('electron');
  const root = process.env.LOCALAPPDATA || path.join(require('node:os').homedir(), 'Library', 'Application Support');
  const profile = path.join(root, 'TokenBots', 'Codex-custom-profile');
  fs.mkdirSync(profile, {recursive: true});
  app.setPath('userData', profile);
}

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
module.exports = {initialize, handle};
