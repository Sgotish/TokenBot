'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const child = require('node:child_process');
const PUBLIC_KEY = "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAIlfRpsrPJ6WNGediIW5pfpJEbjZWb5CfHimHu1omDpk=\n-----END PUBLIC KEY-----\n";
const ENDPOINT = 'https://tokenbots.top/static/windows-ota-v1.json';
const MAX = 4 * 1024 * 1024;
function verify(bytes, publicKey = PUBLIC_KEY) {
  if (bytes.length > MAX) throw Error('Update exceeds size limit');
  const envelope = JSON.parse(bytes);
  const payload = Buffer.from(envelope.payload, 'base64');
  if (!crypto.verify(null, payload, publicKey, Buffer.from(envelope.signature, 'base64'))) throw Error('Invalid update signature');
  const release = JSON.parse(payload);
  if (release.channel !== 'tokenbots-windows-stable-v1' || !Number.isSafeInteger(release.version) || release.version < 1) throw Error('Invalid release');
  if (!Array.isArray(release.files) || !release.files.some(f => f.name === 'apply.ps1')) throw Error('Missing installer');
  const names = new Set();
  for (const f of release.files) {
    if (!/^[a-z][a-z0-9-]{0,60}\.(ps1|cjs|js|json)$/.test(f.name) || names.has(f.name) || typeof f.data !== 'string') throw Error('Invalid file');
    names.add(f.name);
  }
  return release;
}
function atomic(file, data) {
  const temp = file + '.' + crypto.randomUUID() + '.tmp';
  try {fs.writeFileSync(temp, data, {flag:'wx'}); fs.renameSync(temp,file);}
  finally {fs.rmSync(temp,{force:true});}
}
function installed(dir) {
  const file=path.join(dir,'installed');
  if (!fs.existsSync(file)) return 0;
  const n=Number(fs.readFileSync(file,'utf8'));
  if (!Number.isSafeInteger(n) || n<1) throw Error('Invalid installed version');
  return n;
}
function stage(dir, bytes, key) {
  const r=verify(bytes,key);
  if (r.version<=installed(dir)) return;
  atomic(path.join(dir,'release-'+r.version+'.json'),bytes);
}
async function download(dir) {
  const timeout=AbortSignal.timeout(12000);
  const res=await fetch(ENDPOINT,{redirect:'error',signal:timeout,cache:'no-store'});
  if (!res.ok) throw Error('Download failed');
  let length=0; const parts=[];
  for await(const chunk of res.body) {
    length+=chunk.length;
    if(length>MAX) throw Error('Update exceeds size limit');
    parts.push(chunk);
  }
  stage(dir,Buffer.concat(parts));
}
function applyLatest(dir, app, run, key) {
  const candidates=fs.readdirSync(dir).map(n=>/^release-(\d+)\.json$/.exec(n)).filter(Boolean)
    .map(m=>Number(m[1])).filter(n=>n>installed(dir)).sort((a,b)=>b-a);
  if(!candidates.length) return;
  const version=candidates[0], file=path.join(dir,'release-'+version+'.json');
  const r=verify(fs.readFileSync(file),key);
  if(r.version!==version) throw Error('Release version mismatch');
  const temp=fs.mkdtempSync(path.join(dir,'apply-'));
  try {
    for(const f of r.files)fs.writeFileSync(path.join(temp,f.name),Buffer.from(f.data,'base64'),{flag:'wx'});
    run(path.join(temp,'apply.ps1'),app);
    atomic(path.join(dir,'installed'),String(version));
    for(const old of fs.readdirSync(dir).filter(n=>/^release-\d+\.json$/.test(n)&&Number(n.slice(8,-5))<=version))fs.rmSync(path.join(dir,old),{force:true});
  } finally {fs.rmSync(temp,{recursive:true,force:true});}
}
async function main() {
  const [mode,app,input]=process.argv.slice(2);
  if(!path.isAbsolute(app)||!fs.existsSync(path.join(app,'.tokenbots-custom-copy')))throw Error('Unknown installation');
  const dir=path.join(app,'tokenbots-ota');
  fs.mkdirSync(dir,{recursive:true});
  if(mode==='stage')stage(dir,fs.readFileSync(input));
  else if(mode==='fetch')await download(dir);
  else if(mode==='apply')applyLatest(dir,app,(script,target)=>{
    const ps=path.join(process.env.SystemRoot,'System32','WindowsPowerShell','v1.0','powershell.exe');
    child.execFileSync(ps,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',script,'-AppDirectory',target],{stdio:'ignore',windowsHide:true});
  });
  else throw Error('Unknown operation');
}
module.exports={stage,applyLatest,verify};
if(require.main===module)main().catch(()=>{process.exitCode=1;});
