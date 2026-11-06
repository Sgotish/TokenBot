const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const {stage,applyLatest}=require('../integrations/windows-codex/native-menu/ota-client.cjs');
const {prepare,verify}=require('../integrations/windows-codex/native-menu/ota-client.cjs');
test('asset download verifies signature/hash, caches bytes and rejects unsafe endpoints',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ota-assets-'));
 const {privateKey,publicKey}=crypto.generateKeyPairSync('ed25519');
 const data=Buffer.from('archive fixture'),sha=crypto.createHash('sha256').update(data).digest('hex');
 const a={name:'browser-tools.zip',url:'https://tokenbots.top/static/ota-'+sha+'.zip',sha256:sha,size:data.length};
 function signed(asset=a){const payload=Buffer.from(JSON.stringify({channel:'tokenbots-windows-stable-v1',version:10,files:[{name:'apply.ps1',data:'YQ=='}],assets:[asset]}));return Buffer.from(JSON.stringify({payload:payload.toString('base64'),signature:crypto.sign(null,payload,privateKey).toString('base64')}));}
 try {
  assert.throws(()=>verify(signed({...a,url:'https://evil.invalid/file.zip'}),publicKey),/Invalid asset/);
  await assert.rejects(()=>prepare(dir,signed(),publicKey,async()=>new Response('wrong')),/checksum/);
  assert(!fs.existsSync(path.join(dir,'release-10.json')));
  let calls=0; const fetcher=async(url,opts)=>{calls++;assert.equal(opts.redirect,'error');return new Response(data);};
  await prepare(dir,signed(),publicKey,fetcher);await prepare(dir,signed(),publicKey,fetcher);
  assert.equal(calls,1);assert(fs.existsSync(path.join(dir,'release-10.json')));
  const bad=JSON.parse(signed());bad.signature=Buffer.alloc(64).toString('base64');
  await assert.rejects(()=>prepare(dir,Buffer.from(JSON.stringify(bad)),publicKey,fetcher),/signature/);assert.equal(calls,1);
 } finally {fs.rmSync(dir,{recursive:true,force:true});}
});
test('tampering, failed install, retry, same version and downgrade',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ota-test-'));
 const {privateKey,publicKey}=crypto.generateKeyPairSync('ed25519');
 function signed(version){const p=Buffer.from(JSON.stringify({channel:'tokenbots-windows-stable-v1',version,files:[{name:'apply.ps1',data:'YQ=='}]}));return Buffer.from(JSON.stringify({payload:p.toString('base64'),signature:crypto.sign(null,p,privateKey).toString('base64')}));}
 try{
   const bad=JSON.parse(signed(2));bad.payload=JSON.parse(signed(3)).payload;
   assert.throws(()=>stage(dir,Buffer.from(JSON.stringify(bad)),publicKey),/signature/);
   stage(dir,signed(2),publicKey);
   assert.throws(()=>applyLatest(dir,'app',()=>{throw Error('disk full')},publicKey),/disk full/);
   assert(!fs.existsSync(path.join(dir,'installed')));
   let calls=0;const run=f=>{assert.equal(fs.readFileSync(f,'utf8'),'a');calls++};
   applyLatest(dir,'app',run,publicKey);stage(dir,signed(1),publicKey);stage(dir,signed(2),publicKey);
   applyLatest(dir,'app',run,publicKey);assert.equal(calls,1);
   stage(dir,signed(3),publicKey);applyLatest(dir,'app',run,publicKey);assert.equal(calls,2);
 }finally{fs.rmSync(dir,{recursive:true,force:true})}
});
