// node scripts/windows-ota/publish.cjs VERSION RELEASE_DIRECTORY OUTPUT_JSON PRIVATE_PEM
// The release directory contains apply.ps1 plus only the public files it installs.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {verify}=require('../../integrations/windows-codex/native-menu/ota-client.cjs');
const [version,dir,output,privatePem]=process.argv.slice(2);
const files=fs.readdirSync(dir).sort().map(name=>({name,data:fs.readFileSync(path.join(dir,name)).toString('base64')}));
const payload=Buffer.from(JSON.stringify({channel:'tokenbots-windows-stable-v1',version:Number(version),files}));
const bytes=Buffer.from(JSON.stringify({payload:payload.toString('base64'),signature:crypto.sign(null,payload,fs.readFileSync(privatePem)).toString('base64')}));
verify(bytes);
if(fs.existsSync(output) && verify(fs.readFileSync(output)).version>=Number(version))throw Error('Increase release version');
fs.writeFileSync(output+'.tmp',bytes);fs.renameSync(output+'.tmp',output);
