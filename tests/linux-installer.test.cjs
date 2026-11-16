'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process'),http=require('node:http');
const source=path.resolve('delivery/linux-2026111601/TokenBots-Linux');
const linux=require(path.join(source,'linux.cjs'));
function temp(t){const home=fs.mkdtempSync(path.join(os.tmpdir(),'TB Linux space 中文-'));t.after(()=>fs.rmSync(home,{recursive:true,force:true}));return home;}
test('one installer selects each supported distro/CPU and rejects unknown systems before writes',()=>{
  const select=(id,ver,arch)=>cp.spawnSync('bash',['-c','source "$1"; tokenbots_platform "$2" "$3" "$4"','test',path.join(source,'platform.sh'),id,ver,arch],{encoding:'utf8'});
  for(const [id,ver,family] of [['ubuntu','24.04','deb'],['ubuntu','26.04','deb'],['debian','13','deb'],['fedora','43','rpm'],['fedora','44','rpm'],['arch','rolling','arch']]){
    for(const [machine,arch] of [['x86_64','amd64'],['aarch64','arm64']])assert.equal(select(id,ver,machine).stdout.trim(),family+'-'+arch);
  }
  for(const input of [['ubuntu','22.04','x86_64'],['alpine','3.20','x86_64'],['ubuntu','24.04','i686']])assert.notEqual(select(...input).status,0);
});
test('reinstall preserves profile, official data, auth and history and handles spaces',t=>{
  const home=temp(t),p=linux.paths({},home),official=path.join(home,'.codex');fs.mkdirSync(official);fs.writeFileSync(path.join(official,'auth.json'),'official-sentinel');
  const first=linux.install(p,source);fs.writeFileSync(path.join(p.profile,'auth.json'),'private-auth-sentinel');fs.writeFileSync(path.join(p.profile,'history.jsonl'),'conversation-sentinel');
  const target=fs.readlinkSync(path.join(p.base,'current'));const second=linux.install(p,source);
  assert.equal(second.launcher,first.launcher);assert.equal(fs.readlinkSync(path.join(p.base,'current')),target);
  assert.equal(fs.readFileSync(path.join(p.profile,'history.jsonl'),'utf8'),'conversation-sentinel');assert.equal(fs.readFileSync(path.join(p.profile,'auth.json'),'utf8'),'private-auth-sentinel');
  assert.equal(fs.readFileSync(path.join(official,'auth.json'),'utf8'),'official-sentinel');
  assert.equal(fs.statSync(p.profile).mode&0o777,0o700);
  const entry=fs.readFileSync(path.join(p.applications,'tokenbots-codex.desktop'),'utf8');assert(entry.includes('Exec="'));assert(entry.includes('Terminal=false'));
});
test('desktop quoting escapes percent expansions and shell-sensitive paths',()=>{
  assert.equal(linux.execQuote('/tmp/a %F $x "q"/start'),'"/tmp/a %%F \\$x \\"q\\"/start"');
  assert.throws(()=>linux.execQuote('/tmp/a\nExec=bad'));
});
test('real configuration verifies key then writes only isolated profile; invalid key preserves bytes',async t=>{
  const p=linux.paths({},temp(t)),key='synthetic_fixture_not_live_123456';
  const server=http.createServer((req,res)=>{
    if(req.headers.authorization!=='Bearer '+key){res.writeHead(401);res.end('{}');return;}
    res.setHeader('Content-Type','application/json');res.end(JSON.stringify({data:[{id:'gpt-6-astra'}]}));
  });await new Promise(r=>server.listen(0,'127.0.0.1',r));t.after(()=>server.close());
  const opts={origin:'http://127.0.0.1:'+server.address().port,localTest:true};
  await linux.configure(key,p,opts);const auth=fs.readFileSync(path.join(p.profile,'auth.json'),'utf8');assert.equal(JSON.parse(auth).OPENAI_API_KEY,key);
  const before=fs.readFileSync(path.join(p.profile,'config.toml'),'utf8');
  await assert.rejects(linux.configure('invalid_key_12345678',p,opts),/HTTP 401/);
  assert.equal(fs.readFileSync(path.join(p.profile,'auth.json'),'utf8'),auth);assert.equal(fs.readFileSync(path.join(p.profile,'config.toml'),'utf8'),before);
  assert.equal(fs.statSync(path.join(p.profile,'auth.json')).mode&0o777,0o600);
  assert.equal(fs.statSync(path.join(p.profile,'tokenbots-access.json')).mode&0o777,0o600);
  // Public production launch never accepts a test fixture origin.
  assert.throws(()=>linux.launchSpec(p,{binary:'/not-used'}),/Invalid access/);
});
test('package uses pinned HTTPS official downloads and contains no customer access file',()=>{
  const entries=fs.readFileSync(path.join(source,'packages.tsv'),'utf8').trim().split('\n');
  for(const entry of entries){const [,url,hash]=entry.split('\t');assert(url.startsWith('https://persistent.oaistatic.com/codex-app-prod/linux/'));assert.match(hash,/^[0-9a-f]{64}$/);}
  assert(!fs.existsSync(path.join(source,'access.json')));assert(!fs.existsSync(path.join(source,'auth.json')));
});
