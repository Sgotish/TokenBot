const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const {stage,applyLatest}=require('../integrations/windows-codex/native-menu/ota-client.cjs');
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
