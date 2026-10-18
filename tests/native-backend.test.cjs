const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {handle} = require('../integrations/windows-codex/native-menu/backend.cjs');

test('native bridge restricts origins, paths, redirects and credentials', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'tb-native-'));
  const previous = process.resourcesPath;
  process.resourcesPath = directory;
  let calls = 0, redirect = false, observed;
  const server = http.createServer((req, res) => {
    calls++; observed = {url: req.url, auth: req.headers.authorization};
    if (redirect) { res.writeHead(302, {Location: '/unexpected'}); res.end(); return; }
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({selected_pool: 'plus', accounts: []}));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const configPath = path.join(directory, 'tokenbots-native.json');
  const config = {origin: `http://127.0.0.1:${server.address().port}`, key: 'private-test-key', testOnlyLocalOrigin: true};
  fs.writeFileSync(configPath, JSON.stringify(config));
  try {
    const response = await handle(new Request('app://-/tokenbots-native/usage'));
    assert.equal(response.status, 200);
    assert.equal(observed.auth, 'Bearer private-test-key');
    assert.equal(observed.url, '/v1/usage');
    assert(!JSON.stringify(await response.json()).includes(config.key));
    assert.equal((await handle(new Request('app://-/tokenbots-native/usage', {headers: {Origin: 'https://evil.test'}}))).status, 403);
    assert.equal((await handle(new Request('app://other/tokenbots-native/usage'))).status, 403);
    assert.equal((await handle(new Request('app://-/tokenbots-native/anything'))).status, 404);
    assert.equal((await handle(new Request('app://-/tokenbots-native/pool', {method: 'POST', body: '{"pool":"admin"}'}))).status, 400);
    assert.equal(calls, 1);
    assert.equal((await handle(new Request('app://-/tokenbots-native/pool', {method: 'POST', body: '{"pool":"plus"}'}))).status, 200);
    assert.equal(observed.url, '/portal/api/pool');
    redirect = true;
    const failure = await handle(new Request('app://-/tokenbots-native/usage'));
    assert.equal(failure.status, 503);
    assert.equal(calls, 3); // no redirected request with credentials
    assert(!(await failure.text()).includes(config.key));
    fs.writeFileSync(configPath, JSON.stringify({...config, testOnlyLocalOrigin: false}));
    assert.equal((await handle(new Request('app://-/tokenbots-native/usage'))).status, 503);
    assert.equal(calls, 3);
  } finally {
    await new Promise(resolve => server.close(resolve));
    process.resourcesPath = previous;
    fs.rmSync(directory, {recursive: true, force: true});
  }
});
