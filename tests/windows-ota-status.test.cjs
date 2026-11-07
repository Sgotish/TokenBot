const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const ota=require('../integrations/windows-codex/native-menu/ota-client.cjs');
const {privateKey,publicKey}=crypto.generateKeyPairSync('ed25519');
function signed(version){const payload=Buffer.from(JSON.stringify({channel:'tokenbots-windows-stable-v1',version,files:[{name:'apply.ps1',data:'YQ=='}]}));return Buffer.from(JSON.stringify({payload:payload.toString('base64'),signature:crypto.sign(null,payload,privateKey).toString('base64')}));}
test('manual check distinguishes new/latest/offline/rollback and installation timestamps',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'tb-status-'));
 try{
  const remote=async()=>new Response(signed(20));
  assert.equal((await ota.check(dir,publicKey,remote)).state,'available');
  assert(!fs.existsSync(path.join(dir,'release-20.json')),'checking must not install or stage');
  assert.equal(ota.state(dir).lastUpdatedAt,null);
  await ota.download(dir,publicKey,remote);
  assert.equal(ota.state(dir).state,'ready');assert.equal(ota.state(dir).installedVersion,0);
  ota.applyLatest(dir,'app',()=>{},publicKey);
  const receipt=ota.state(dir).lastUpdatedAt; assert(Number.isFinite(Date.parse(receipt)));
  const latest=await ota.check(dir,publicKey,remote);
  assert.equal(latest.state,'latest');assert.equal(latest.installedVersion,20);assert.equal(latest.lastUpdatedAt,receipt);
  await assert.rejects(ota.check(dir,publicKey,async()=>{throw Error('offline');}));
  assert.equal(ota.state(dir).state,'error');assert.equal(ota.state(dir).lastCheckedAt,latest.lastCheckedAt);
  assert.equal(ota.state(dir).lastUpdatedAt,receipt);
  await assert.rejects(ota.check(dir,publicKey,async()=>new Response(signed(19))),/older/);
  assert.equal(ota.state(dir).state,'error');
  await ota.download(dir,publicKey,async()=>new Response(signed(21)));
  assert.throws(()=>ota.applyLatest(dir,'app',()=>{throw Error('disk');},publicKey));
  assert.equal(ota.state(dir).installedVersion,20);assert.equal(ota.state(dir).lastUpdatedAt,receipt);
  await ota.exclusive(dir,async()=>{
    await assert.rejects(ota.exclusive(dir,async()=>{}),/progress/);
  });
  assert(!fs.existsSync(path.join(dir,'operation.lock')));
  fs.writeFileSync(path.join(dir,'status.json'),JSON.stringify({state:'downloading',lastAttemptAt:'2020-01-01T00:00:00Z'}));
  assert.equal(ota.state(dir).state,'error','interrupted updater cannot leave button disabled forever');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('updater status is available without API credentials and cannot be called cross-origin',async()=>{
 const app=fs.mkdtempSync(path.join(os.tmpdir(),'tb-status-api-'));
 const previous=process.resourcesPath; process.resourcesPath=path.join(app,'resources');
 fs.mkdirSync(process.resourcesPath);fs.writeFileSync(path.join(app,'.tokenbots-custom-copy'),'');
 fs.copyFileSync(path.resolve('integrations/windows-codex/native-menu/ota-client.cjs'),path.join(app,'ota-client.cjs'));
 const {handle}=require('../integrations/windows-codex/native-menu/backend.cjs');
 try{
  const result=await handle(new Request('app://-/tokenbots-native/update'));
  assert.equal(result.status,200); assert.equal((await result.json()).installedVersion,0);
  assert.equal((await handle(new Request('app://-/tokenbots-native/update/check',{method:'GET'}))).status,405);
  assert.equal((await handle(new Request('app://-/tokenbots-native/update/download',{method:'POST',headers:{Origin:'https://evil.test'}}))).status,403);
 }finally{process.resourcesPath=previous;fs.rmSync(app,{recursive:true,force:true});}
});
