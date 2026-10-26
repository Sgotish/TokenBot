#!/usr/bin/env node
'use strict';
const fs=require('node:fs'), path=require('node:path'), os=require('node:os');
const crypto=require('node:crypto'), cp=require('node:child_process');
const {parse,stringify}=require('smol-toml');
const PROVIDER='tokenbots_cross_platform';
const CATALOG=require('../model-catalog/models.json').models;
const hash=v=>crypto.createHash('sha256').update(v??'<absent>').digest('hex');
const read=p=>fs.existsSync(p)?fs.readFileSync(p,'utf8'):null;
function write(file,value){
  if(fs.existsSync(file)&&fs.lstatSync(file).isSymbolicLink())throw Error('Refusing symlink configuration.');
  fs.mkdirSync(path.dirname(file),{recursive:true,mode:0o700});
  const tmp=file+'.'+crypto.randomUUID()+'.tmp';
  try{
    fs.writeFileSync(tmp,value,{mode:0o600,flag:'wx'});
    if(process.platform==='win32')cp.execFileSync('icacls.exe',[tmp,'/inheritance:r','/grant:r',`${os.userInfo().username}:(F)`],{stdio:'pipe'});
    fs.renameSync(tmp,file);
  }finally{if(fs.existsSync(tmp))fs.unlinkSync(tmp);}
}
function validateAccess(d,localTest=false){
  const u=new URL(d.public_origin);
  if(!(u.protocol==='https:'||(localTest&&u.protocol==='http:'&&u.hostname==='127.0.0.1'))||u.username||u.password||u.pathname!=='/'||u.search||u.hash||d.base_url!==u.origin+'/v1'||!/^[A-Za-z0-9_-]{16,256}$/.test(d.key))throw Error('Invalid access file. Expected HTTPS origin, /v1 URL and private key.');
  return {public_origin:u.origin,base_url:d.base_url,key:d.key,label:typeof d.label==='string'?d.label:'TokenBots'};
}
function defaultHome(target){return target==='cli'?path.join(os.homedir(),'.tokenbots-codex'):path.resolve(process.env.CODEX_HOME||path.join(os.homedir(),'.codex'));}
function mergeTables(base,extra){
  const table=v=>v && (Object.getPrototypeOf(v)===Object.prototype||Object.getPrototypeOf(v)===null);
  for(const [key,value] of Object.entries(extra)){
    if(table(value)&&table(base[key]))mergeTables(base[key],value);
    else base[key]=value;
  }
  return base;
}
function mergeConfig(old,access,target,activeProfile){
  let d;try{d=parse(old||'');}catch{throw Error('Invalid existing TOML. Nothing changed.');}
  if(d.profile){
    if(typeof activeProfile!=='string')throw Error('Invalid active profile. Cannot configure without preserving its settings.');
    try{d=mergeTables(d,parse(activeProfile));}catch{throw Error('Invalid active profile TOML. Nothing changed.');}
    // Preserve the effective profile settings in the root, then select this connection.
    // The original profile file is untouched; rollback restores its selection byte-for-byte.
    delete d.profile;
  }
  const selected=CATALOG.find(m=>m.id===d.model)||CATALOG.find(m=>m.id==='gpt-6-astra');
  d.model=selected.id;d.model_reasoning_effort=selected.reasoning_efforts.includes(d.model_reasoning_effort)?d.model_reasoning_effort:'high';d.model_provider=PROVIDER;delete d.service_tier;
  d.model_providers||={};d.model_providers[PROVIDER]={name:access.label,base_url:access.base_url,wire_api:'responses',
    ...(target==='cli'?{env_key:'TOKENBOTS_API_KEY'}:{experimental_bearer_token:access.key}),
    requires_openai_auth:false,supports_websockets:false,request_max_retries:0,stream_max_retries:0,stream_idle_timeout_ms:300000,
    capabilities:{remote_compaction:'v2'}};
  return stringify(d);
}
async function request(a,endpoint,body,timeout=15000){
  const r=await fetch(a.public_origin+endpoint,{method:body?'POST':'GET',redirect:'error',signal:AbortSignal.timeout(timeout),
    headers:{Authorization:'Bearer '+a.key,Origin:a.public_origin,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
  if(!r.ok)throw Error(`Service returned HTTP ${r.status}. No automatic retry; check usage and network.`);
  return r;
}
async function configure({home,access,target,localTest=false}){
  if(!['cli','desktop'].includes(target))throw Error('Choose cli or desktop.');
  access=validateAccess(access,localTest);
  const file=path.join(home,'config.toml'),af=path.join(home,'tokenbots-access.json');
  const before=read(file),beforeAccess=read(af);
  let profile;try{profile=parse(before||'').profile;}catch{throw Error('Invalid existing TOML. Nothing changed.');}
  if(profile && (typeof profile!=='string'||profile==='..'||/[\\/]/.test(profile)))throw Error('Invalid profile filename. Nothing changed.');
  const activeProfile=profile?read(path.join(home,profile+'.config.toml')):undefined;
  const next=mergeConfig(before,access,target,activeProfile);
  const models=await(await request(access,'/v1/models')).json();
  if(!models.data?.some(m=>m.id===parse(next).model))throw Error('Model unavailable. Nothing changed.');
  const na=JSON.stringify({...access,target},null,2)+'\n';
  const record={before,beforeAccess,installed:hash(next),installedAccess:hash(na),target,created:new Date().toISOString()};
  const backup=path.join(home,'.tokenbots-setup',Date.now()+'-'+crypto.randomUUID()+'.json');
  if(read(file)!==before||read(af)!==beforeAccess)throw Error('Configuration changed during network validation. Run setup again.');
  write(backup,JSON.stringify(record));
  try{write(af,na);write(file,next);}catch(e){if(beforeAccess===null){if(fs.existsSync(af))fs.unlinkSync(af);}else write(af,beforeAccess);record.rolled_back=true;write(backup,JSON.stringify(record));throw e;}
  return {home,backup,target};
}
function rollback(home){
  const dir=path.join(home,'.tokenbots-setup');
  const files=fs.existsSync(dir)?fs.readdirSync(dir).filter(x=>x.endsWith('.json')).sort().reverse():[];
  const latest=files.map(x=>[path.join(dir,x),JSON.parse(read(path.join(dir,x)))]).find(([,s])=>!s.rolled_back);
  if(!latest)throw Error('No outstanding TokenBots configuration to restore.');
  const [backup,s]=latest,c=path.join(home,'config.toml'),a=path.join(home,'tokenbots-access.json');
  if(hash(read(c))!==s.installed||hash(read(a))!==s.installedAccess)throw Error('Configuration changed after setup. Restore manually from backup to preserve later edits.');
  for(const [f,v]of[[c,s.before],[a,s.beforeAccess]]){if(v===null)fs.unlinkSync(f);else write(f,v);}
  s.rolled_back=true;write(backup,JSON.stringify(s));return {restored:true,backup};
}
function resolveCodex(explicit){
  const dirs=(process.env.PATH||'').split(path.delimiter);
  const candidates=explicit?[path.resolve(explicit)]:dirs.flatMap(d=>process.platform==='win32'?[path.join(d,'codex.exe'),path.join(d,'node_modules','@openai','codex','bin','codex.js')]:[path.join(d,'codex')]);
  if(!explicit)candidates.unshift(path.join(os.homedir(),'.tokenbots-tools','node_modules','@openai','codex','bin','codex.js'));
  if(!explicit&&process.platform==='darwin')candidates.push('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex','/Applications/Codex.app/Contents/Resources/codex');
  const file=candidates.find(p=>fs.existsSync(p)&&fs.statSync(p).isFile());
  if(!file)throw Error('Codex CLI not found. Install the official CLI or pass --codex PATH.');
  if(/\.(cmd|bat)$/i.test(file))throw Error('Select codex.exe or @openai/codex/bin/codex.js, not a shell wrapper.');
  return file.endsWith('.js')?{command:process.execPath,args:[file]}:{command:file,args:[]};
}
function installCli(){
  const candidates=[path.join(path.dirname(process.execPath),'node_modules','npm','bin','npm-cli.js'),
    ...(process.env.PATH||'').split(path.delimiter).map(d=>path.join(d,'npm'))];
  const found=candidates.find(p=>fs.existsSync(p)&&fs.realpathSync(p).endsWith('npm-cli.js'));
  if(!found)throw Error('Node.js npm CLI not found. Install Node.js LTS including npm.');
  const result=cp.spawnSync(process.execPath,[fs.realpathSync(found),'install','--prefix',path.join(os.homedir(),'.tokenbots-tools'),'--ignore-scripts','--no-audit','--no-fund','@openai/codex@0.163.0'],{stdio:'inherit',timeout:300000});
  if(result.status!==0)throw Error('Codex CLI not found: installation did not finish. Check npm network access.');
  console.log('Installed validated Codex CLI 0.163.0 in ~/.tokenbots-tools. Existing global CLI unchanged.');
}
function launch(home,args,explicit){
  const a=validateAccess(JSON.parse(read(path.join(home,'tokenbots-access.json'))||'{}'));
  if(parse(read(path.join(home,'config.toml'))||'').model_provider!==PROVIDER)throw Error('This home does not select TokenBots. Run setup first.');
  const b=resolveCodex(explicit),child=cp.spawn(b.command,[...b.args,...args],{stdio:'inherit',env:{...process.env,CODEX_HOME:home,TOKENBOTS_API_KEY:a.key},shell:false});
  child.on('error',()=>{console.error('Unable to start Codex CLI.');process.exitCode=1;});child.on('exit',code=>{process.exitCode=code??1;});return child;
}
function displayUsage(d){
  const lines=[`TokenBots | pool: ${d.selected_pool}`,`Checked: ${new Date().toISOString()}`];
  for(const a of d.accounts||[]){lines.push(a.label);for(const w of a.windows||[]){
    const value=typeof w.remaining_percent==='number'?w.remaining_percent+'%':'unknown';
    lines.push(`  ${w.label}: ${value}${w.stale||a.snapshot_stale||d.snapshot_stale?' [stale]':''}; resets: ${w.resets_at||'unknown'}`);
  }}
  lines.push('Shared upstream subscription limits; no platform spending cap does not mean unlimited upstream usage.');return lines.join('\n');
}
async function probe(a){
  const r=await request(a,'/v1/responses',{model:'gpt-6.1-sol',stream:true,store:false,reasoning:{effort:'low'},instructions:'Reply with the exact answer only.',input:[{role:'user',content:'What is 17 + 25? Reply with 42 only.'}]},120000);
  const text=await r.text(),events=text.split('\n').filter(l=>l.startsWith('data: {')).map(l=>JSON.parse(l.slice(6)));
  const done=events.find(e=>e.type==='response.completed'),answer=events.filter(e=>e.type==='response.output_text.delta').map(e=>e.delta).join('').trim();
  if(!done||answer!=='42')throw Error('Inference did not produce a completed, correct answer.');
  return {pass:true,answer,model:'gpt-6.1-sol',usage:done.response?.usage};
}
async function main(argv=process.argv.slice(2)){
  if(Number(process.versions.node.split('.')[0])<20)throw Error('Node.js 20 or newer required.');
  const command=argv.shift()||'help',opts={},rest=[];
  while(argv.length){const arg=argv.shift();if(arg==='--'){rest.push(...argv);break;}
    if(['--home','--target','--access','--codex'].includes(arg)){if(!argv.length)throw Error('Missing option value.');opts[arg.slice(2)]=argv.shift();}
    else if(arg==='--watch')opts.watch=true;else rest.push(arg);}
  const target=opts.target||'cli',home=path.resolve(opts.home||defaultHome(target));
  if(command==='help')return console.log('TokenBots: install-cli | setup --target cli|desktop --access access.json | run -- [Codex arguments] | usage [--watch] | pool auto|plus|pro | probe | doctor | rollback\nOptions: --home PATH, --target cli|desktop, --codex PATH\nCLI uses ~/.tokenbots-codex. Desktop uses CODEX_HOME or ~/.codex. Close desktop before setup/rollback.');
  if(command==='install-cli')return installCli();
  if(command==='doctor'){let cli='not found';try{const b=resolveCodex(opts.codex);cli=cp.execFileSync(b.command,[...b.args,'--version'],{encoding:'utf8',timeout:15000}).trim();}catch{}
    return console.log(JSON.stringify({os:process.platform,arch:process.arch,wsl:!!process.env.WSL_DISTRO_NAME,node:process.version,cli,home,target,configured:fs.existsSync(path.join(home,'tokenbots-access.json'))},null,2));}
  if(command==='setup'){if(!opts.access)throw Error('Provide --access access.json (never a key in command history).');
    console.log(JSON.stringify(await configure({home,target,access:JSON.parse(fs.readFileSync(opts.access,'utf8'))}),null,2));return console.log('Configured. Restart desktop or use TokenBots CLI launcher. Start a new conversation.');}
  if(command==='rollback')return console.log(JSON.stringify(rollback(home),null,2));
  if(command==='run'){launch(home,rest,opts.codex);return;}
  const a=validateAccess(JSON.parse(read(path.join(home,'tokenbots-access.json'))||'{}'));
  if(command==='probe')return console.log(JSON.stringify(await probe(a),null,2));
  if(command==='pool'){if(!['auto','plus','pro'].includes(rest[0]))throw Error('Choose auto, plus or pro.');
    console.log(await(await request(a,'/portal/api/pool',{pool:rest[0]})).text());return console.log('Start a new conversation. Pool choice applies to this key on all devices.');}
  if(command==='usage'){do{console.log(displayUsage(await(await request(a,'/v1/usage')).json()));if(opts.watch)await new Promise(r=>setTimeout(r,30000));}while(opts.watch);return;}
  throw Error('Unknown command. Run help.');
}
module.exports={configure,rollback,mergeConfig,validateAccess,defaultHome,displayUsage,resolveCodex,request,probe,main,PROVIDER};
if(require.main===module)main().catch(e=>{const allowed=/^(Invalid |Choose |Model unavailable|Service returned|No outstanding|Configuration changed|Codex CLI not found|Select codex|Provide |Unknown command|Node.js |Inference did not|Missing option|Refusing |This home)/;
  console.error(allowed.test(e.message)?e.message:'Operation failed. Check network, file permissions and access configuration. Credentials were not printed.');process.exitCode=1;});
