const {test}=require('node:test'), assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {install}=require('../integrations/windows-codex/browser-tools/install.cjs');
const toml=require('../integrations/windows-codex/browser-tools/node_modules/@iarna/toml');
test('native profile configuration is preserved; installation is idempotent',()=>{
 const home=fs.mkdtempSync(path.join(os.tmpdir(),'tb-browser-'));
 try {
  const file=path.join(home,'config.toml');
  const original='model="gpt-6-astra"\nmodel_reasoning_effort="high"\n[mcp_servers.existing]\ncommand="keep-me"\n[model_providers.tokenbots]\nbase_url="https://example.invalid/v1"\n';
  fs.writeFileSync(file,original);
  install(home,process.execPath); const first=fs.readFileSync(file,'utf8');
  install(home,process.execPath); assert.equal(fs.readFileSync(file,'utf8'),first);
  const parsed=toml.parse(first); delete parsed.mcp_servers.tokenbots_browser; delete parsed.mcp_servers.tokenbots_desktop;
  assert.deepEqual(parsed,toml.parse(original));
  assert.equal(fs.readdirSync(home).filter(x=>x.startsWith('config.toml.before-browser')).length,1);
  assert.ok(!fs.existsSync(path.join(home,'skills/tokenbots-project-checkpoints/SKILL.md')));
 } finally {fs.rmSync(home,{recursive:true,force:true});}
});
test('malformed configuration is not rewritten',()=>{
 const home=fs.mkdtempSync(path.join(os.tmpdir(),'tb-browser-'));
 try { const file=path.join(home,'config.toml'); fs.writeFileSync(file,'broken = [');
  assert.throws(()=>install(home,process.execPath)); assert.equal(fs.readFileSync(file,'utf8'),'broken = [');
 } finally {fs.rmSync(home,{recursive:true,force:true});}
});
test('a user-owned skill is never replaced',()=>{
 const home=fs.mkdtempSync(path.join(os.tmpdir(),'tb-browser-'));
 try {const dir=path.join(home,'skills/tokenbots-browser-check');fs.mkdirSync(dir,{recursive:true});
  fs.writeFileSync(path.join(dir,'SKILL.md'),'custom'); fs.writeFileSync(path.join(home,'config.toml'),'model="keep"\n');
  install(home,process.execPath);
  assert.equal(fs.readFileSync(path.join(dir,'SKILL.md'),'utf8'),'custom');
  assert.equal(toml.parse(fs.readFileSync(path.join(home,'config.toml'),'utf8')).model,'keep');
 } finally {fs.rmSync(home,{recursive:true,force:true});}
});
test('OTA removes only owned trial retry overrides and enables compaction',()=>{
 const home=fs.mkdtempSync(path.join(os.tmpdir(),'tb-desktop-config-'));
 try {
 const file=path.join(home,'config.toml');fs.writeFileSync(file,'model="gpt-6-astra"\nmodel_reasoning_effort="high"\n[model_providers.tokenbots_partner_20261016]\nrequest_max_retries=0\nstream_max_retries=0\nexperimental_bearer_token="SYNTHETIC"\n[model_providers.tokenbots_partner_20261016.capabilities]\nremote_compaction="unsupported"\n');
 install(home,process.execPath);const first=fs.readFileSync(file,'utf8');install(home,process.execPath);assert.equal(fs.readFileSync(file,'utf8'),first);
 const c=toml.parse(first);assert.equal(c.model,'gpt-6-astra');assert.equal(c.model_reasoning_effort,'high');
 const p=c.model_providers.tokenbots_partner_20261016;assert.equal(p.experimental_bearer_token,'SYNTHETIC');assert.equal(p.request_max_retries,undefined);assert.equal(p.stream_max_retries,undefined);assert.equal(p.capabilities.remote_compaction,'v2');assert.ok(c.mcp_servers.tokenbots_desktop);
 }finally{fs.rmSync(home,{recursive:true,force:true});}
});
