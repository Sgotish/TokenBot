'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const child = require('node:child_process');
const PUBLIC_KEY = "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAIlfRpsrPJ6WNGediIW5pfpJEbjZWb5CfHimHu1omDpk=\n-----END PUBLIC KEY-----\n";
const ENDPOINT = 'https://tokenbots.top/static/windows-ota-v1.json';
const MAX = 4 * 1024 * 1024;
const MAX_ASSET = 24 * 1024 * 1024;
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
  if (release.assets !== undefined) {
    if (!Array.isArray(release.assets) || release.assets.length>2) throw Error('Invalid assets');
    const assetNames=new Set();
    for(const a of release.assets) {
      if(!/^[a-z][a-z0-9-]{0,60}\.zip$/.test(a.name) || assetNames.has(a.name) ||
        !/^[a-f0-9]{64}$/.test(a.sha256) || !Number.isSafeInteger(a.size) || a.size<1 || a.size>MAX_ASSET ||
        a.url !== 'https://tokenbots.top/static/ota-'+a.sha256+'.zip')throw Error('Invalid asset');
      assetNames.add(a.name);
    }
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
function state(dir) {
  let value = {};
  try { value = JSON.parse(fs.readFileSync(path.join(dir,'status.json'),'utf8')); } catch {}
  let receipt = {};
  try { receipt = JSON.parse(fs.readFileSync(path.join(dir,'receipt.json'),'utf8')); } catch {}
  return {...value, installedVersion:installed(dir), lastUpdatedAt:receipt.installedAt || null};
}
function saveState(dir, patch) {
  const value={...state(dir),...patch};
  atomic(path.join(dir,'status.json'),JSON.stringify(value));
  return state(dir);
}
async function exclusive(dir, action) {
  const lock=path.join(dir,'operation.lock');
  let fd;
  try { fd=fs.openSync(lock,'wx'); }
  catch(e) {
    if(e.code!=='EEXIST')throw e;
    const pid=Number(fs.readFileSync(lock,'utf8'));
    // An empty lock may be in the process of being created. Never steal it.
    if(!Number.isInteger(pid)||pid<1)throw Error('Update already in progress');
    try { process.kill(pid,0); throw Error('Update already in progress'); }
    catch(err) { if(err.code!=='ESRCH')throw err; }
    fs.unlinkSync(lock); fd=fs.openSync(lock,'wx');
  }
  fs.writeFileSync(fd,String(process.pid));
  try { return await action(); }
  finally { fs.closeSync(fd); fs.rmSync(lock,{force:true}); }
}
async function check(dir,key,fetcher=fetch) {
  saveState(dir,{state:'checking',error:null,lastAttemptAt:new Date().toISOString()});
  try {
    const bytes=await readDownload(ENDPOINT,MAX,12000,fetcher);
    const r=verify(bytes,key);
    // A stale/rolled-back server feed must not claim that this device is latest.
    if(r.version<installed(dir))throw Error('Update feed is older than this installation');
    atomic(path.join(dir,'checked.json'),bytes);
    const ready=fs.existsSync(path.join(dir,'release-'+r.version+'.json')) &&
      (r.assets||[]).every(a=>assetValid(dir,a));
    return saveState(dir,{state:r.version===installed(dir)?'latest':ready?'ready':'available',
      latestVersion:r.version,lastCheckedAt:new Date().toISOString(),error:null});
  } catch(e) {
    saveState(dir,{state:'error',error:'检查失败，请检查网络后重试；尚未确认最新版本。'}); throw e;
  }
}
function stage(dir, bytes, key) {
  const r=verify(bytes,key);
  if (r.version<=installed(dir)) return;
  atomic(path.join(dir,'release-'+r.version+'.json'),bytes);
}
async function readDownload(url,limit,timeout,fetcher=fetch) {
  const res=await fetcher(url,{redirect:'error',signal:AbortSignal.timeout(timeout),cache:'no-store'});
  if (!res.ok) throw Error('Download failed');
  let length=0; const parts=[];
  for await(const chunk of res.body) {
    length+=chunk.length;
    if(length>limit) throw Error('Update exceeds size limit');
    parts.push(chunk);
  }
  return Buffer.concat(parts);
}
function assetPath(dir,a){return path.join(dir,'assets',a.sha256+'.zip');}
function assetValid(dir,a){
  const file=assetPath(dir,a);
  return fs.existsSync(file)&&fs.statSync(file).size===a.size&&crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')===a.sha256;
}
async function prepare(dir,bytes,key,fetcher=fetch){
  const r=verify(bytes,key);
  if(r.version<=installed(dir))return;
  for(const a of r.assets || []){
    if(assetValid(dir,a))continue;
    const data=await readDownload(a.url,a.size,60000,fetcher);
    if(data.length!==a.size || crypto.createHash('sha256').update(data).digest('hex')!==a.sha256)throw Error('Asset checksum mismatch');
    fs.mkdirSync(path.join(dir,'assets'),{recursive:true});atomic(assetPath(dir,a),data);
  }
  stage(dir,bytes,key);
  saveState(dir,{state:'ready',version:r.version,latestVersion:r.version,error:null});
}
async function download(dir,key,fetcher=fetch) {
  const result=await check(dir,key,fetcher);
  if(result.state==='latest')return result;
  saveState(dir,{state:'downloading',error:null});
  try {
    await prepare(dir,fs.readFileSync(path.join(dir,'checked.json')),key,fetcher);
    return state(dir);
  } catch(e) { saveState(dir,{state:'error',error:'下载或校验失败，当前版本未改变，请重试。'}); throw e; }
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
    atomic(path.join(dir,'receipt.json'),JSON.stringify({version,installedAt:new Date().toISOString()}));
    saveState(dir,{state:'installed',version,error:null});
    for(const old of fs.readdirSync(dir).filter(n=>/^release-\d+\.json$/.test(n)&&Number(n.slice(8,-5))<=version))fs.rmSync(path.join(dir,old),{force:true});
  } catch(e) { saveState(dir,{state:'error',error:'更新安装失败，已保留原版本，请重试或联系客服。'}); throw e; }
  finally {fs.rmSync(temp,{recursive:true,force:true});}
}
async function main() {
  const [mode,app,input]=process.argv.slice(2);
  if(!path.isAbsolute(app)||!fs.existsSync(path.join(app,'.tokenbots-custom-copy')))throw Error('Unknown installation');
  const dir=path.join(app,'tokenbots-ota');
  fs.mkdirSync(dir,{recursive:true});
  await exclusive(dir,async()=>{
  if(mode==='check')await check(dir);
  else if(mode==='stage')stage(dir,fs.readFileSync(input));
  else if(mode==='fetch')await download(dir);
  else if(mode==='apply')applyLatest(dir,app,(script,target)=>{
    const ps=path.join(process.env.SystemRoot,'System32','WindowsPowerShell','v1.0','powershell.exe');
    child.execFileSync(ps,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',script,'-AppDirectory',target],{stdio:'ignore',windowsHide:true});
  });
  else throw Error('Unknown operation');
  });
}
module.exports={stage,applyLatest,verify,prepare,download,assetValid,state,check,exclusive};
if(require.main===module)main().catch(()=>{process.exitCode=1;});
