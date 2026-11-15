const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const ota=require('../integrations/windows-codex/native-menu/ota-client.cjs');
const {privateKey,publicKey}=crypto.generateKeyPairSync('ed25519');
const data=Buffer.from('synthetic signed MSIX artifact');
const sha=crypto.createHash('sha256').update(data).digest('hex');
const desktop={applicationVersion:'26.1111.21308',packageVersion:'26.1111.2228.0',size:data.length,sha256:sha,url:`https://pilot.tokenbots.top/downloads/ChatGPT-${process.arch}-${sha}.msix`};
function signed(d=desktop){const payload=Buffer.from(JSON.stringify({channel:'tokenbots-windows-stable-v1',version:20,files:[{name:'apply.ps1',data:'YQ=='}],desktop:{[process.arch]:d}}));return Buffer.from(JSON.stringify({payload:payload.toString('base64'),signature:crypto.sign(null,payload,privateKey).toString('base64')}));}
test('desktop download is bounded, integrity checked, cached and never staged on failure',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'tb-desktop-download-'));
 try{
  assert.throws(()=>ota.verify(signed({...desktop,url:'https://example.com/other.msix'}),publicKey),/Invalid desktop/);
  assert.throws(()=>ota.verify(signed({...desktop,size:2*1024**3}),publicKey),/Invalid desktop/);
  await assert.rejects(ota.prepare(dir,signed(),publicKey,async()=>new Response(data.subarray(1))),/checksum/);
  await assert.rejects(ota.prepare(dir,signed(),publicKey,async()=>new Response(Buffer.concat([data,data]))),/size limit/);
  assert(!fs.existsSync(path.join(dir,'release-20.json')));
  assert.deepEqual(fs.readdirSync(path.join(dir,'assets')),[]);
  let calls=0;
  const fetcher=async(url,options)=>{calls++;assert.equal(url,desktop.url);assert.equal(options.redirect,'error');return new Response(data);};
  await ota.prepare(dir,signed(),publicKey,fetcher);await ota.prepare(dir,signed(),publicKey,fetcher);
  assert.equal(calls,1);assert(await ota.desktopValid(dir,desktop));
  fs.writeFileSync(path.join(dir,'assets',sha+'.msix'),Buffer.alloc(data.length));
  assert.equal(await ota.desktopValid(dir,desktop),false);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('desktop handover records both installations and checks actual base version',async()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'tb-desktop-handover-'));
 const app=path.join(root,'old','app'),next=path.join(root,'new','app'),dir=path.join(app,'tokenbots-ota');
 fs.mkdirSync(dir,{recursive:true});fs.mkdirSync(path.join(next,'resources'),{recursive:true});
 fs.writeFileSync(path.join(next,'.tokenbots-custom-copy'),'');
 fs.writeFileSync(path.join(next,'resources','owl-app.ini'),'[Owl]\r\nAppVersion=26.1111.21308\r\n');
 try{
  ota.stage(dir,signed(),publicKey);
  ota.applyLatest(dir,app,(_script,_app,version)=>{assert.equal(version,20);fs.writeFileSync(path.join(app,'tokenbots-next-app.json'),JSON.stringify({version,app:next}));},publicKey);
  const nextDir=path.join(next,'tokenbots-ota');
  assert.equal(ota.state(nextDir).installedVersion,20);assert.equal(ota.state(nextDir).desktopVersion,'26.1111.21308');
  assert.equal((await ota.check(nextDir,publicKey,async()=>new Response(signed()))).state,'latest');
  fs.writeFileSync(path.join(next,'resources','owl-app.ini'),'AppVersion=26.1016.51333\n');
  await assert.rejects(ota.check(nextDir,publicKey,async()=>new Response(signed())),/does not match/);
  assert.equal(ota.state(nextDir).state,'error');
 }finally{fs.rmSync(root,{recursive:true,force:true});}
});
