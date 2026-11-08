'use strict';
// Repair only the local metadata index through Codex's own scan-and-repair API.
// Never rewrite/delete rollouts, change providers, or send a model request.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawn} = require('node:child_process');

async function repair(cli, home, timeoutMs = 20000) {
  const child = spawn(cli, ['app-server', '--stdio'], {
    cwd: home, env: {...process.env, CODEX_HOME: home},
    windowsHide: true, stdio: ['pipe', 'pipe', 'ignore'],
  });
  let buffer = '', seq = 0;
  const pending = new Map();
  child.stdout.setEncoding('utf8');
  const fail = () => { for (const p of pending.values()) p.reject(Error('history_scan_unavailable')); pending.clear(); };
  child.on('error', fail); child.on('exit', fail);
  child.stdin.on('error', fail);
  child.stdout.on('data', chunk => {
    buffer += chunk.toString('utf8');
    if (buffer.length > 4 * 1024 * 1024) { fail(); child.kill(); return; }
    let at;
    while ((at = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, at); buffer = buffer.slice(at + 1);
      let message; try { message = JSON.parse(line); } catch { continue; }
      const p = pending.get(message.id);
      if (p) { pending.delete(message.id); message.error ? p.reject(Error('history_scan_rejected')) : p.resolve(message.result); }
    }
  });
  const request = (method, params) => new Promise((resolve, reject) => {
    const id = ++seq; pending.set(id, {resolve, reject});
    child.stdin.write(JSON.stringify({id, method, params}) + '\n');
  });
  const timer = setTimeout(() => { fail(); child.kill(); }, timeoutMs);
  try {
    await request('initialize', {clientInfo: {name: 'tokenbots_history_repair', version: '1.0'}, capabilities: {experimentalApi: true}});
    child.stdin.write('{"method":"initialized"}\n');
    const counts = {};
    for (const archived of [false, true]) {
      // This API repairs metadata from durable JSONL files. It does not resume
      // conversations or change archive status. A single page triggers repair.
      const result = await request('thread/list', {limit: 100, archived,
        modelProviders: [], useStateDbOnly: false});
      counts[archived ? 'archived_page_count' : 'active_page_count'] = result.data.length;
    }
    return {status: 'completed', checked_at: new Date().toISOString(), ...counts};
  } finally { clearTimeout(timer); child.kill(); }
}

async function main(app) {
  if (!app || !fs.existsSync(path.join(app, '.tokenbots-custom-copy'))) throw Error('unknown_copy');
  const access = JSON.parse(fs.readFileSync(path.join(app, 'resources', 'tokenbots-native.json'), 'utf8').replace(/^\uFEFF/, ''));
  const id = crypto.createHash('sha256').update(access.key).digest('hex').slice(0, 16);
  const home = path.join(process.env.USERPROFILE, '.tokenbots-native-homes', id);
  if (!process.env.CODEX_HOME || path.resolve(process.env.CODEX_HOME).toLowerCase() !== path.resolve(home).toLowerCase()) throw Error('profile_mismatch');
  let result;
  try { result = await repair(path.join(app, 'resources', 'codex.exe'), home); }
  catch { result = {status: 'incomplete', checked_at: new Date().toISOString()}; }
  // No conversation text, IDs, paths, key or model response in diagnostics.
  fs.writeFileSync(path.join(home, 'tokenbots-history-check.json'), JSON.stringify(result));
  if (result.status !== 'completed') process.exitCode = 1;
}
module.exports = {repair};
if (require.main === module) main(process.argv[2]).catch(() => { process.exitCode = 1; });
