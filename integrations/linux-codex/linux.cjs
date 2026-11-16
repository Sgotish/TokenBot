#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process'),crypto=require('node:crypto');
const client=require('./tokenbots.cjs');
const VERSION='2026111601';
function paths(env=process.env,home=os.homedir()) {
  const base=path.resolve(env.XDG_DATA_HOME||path.join(home,'.local/share'),'tokenbots-codex-linux');
  return {base,profile:path.join(base,'profile'),ui:path.join(base,'desktop'),applications:path.resolve(env.XDG_DATA_HOME||path.join(home,'.local/share'),'applications')};
}
function privateDir(p){
  if(fs.existsSync(p)&&fs.lstatSync(p).isSymbolicLink())throw Error('目录不能是符号链接：'+p);
  fs.mkdirSync(p,{recursive:true,mode:0o700});fs.chmodSync(p,0o700);
}
function atomic(file,content,mode=0o600){
  if(fs.existsSync(file)&&fs.lstatSync(file).isSymbolicLink())throw Error('配置文件不能是符号链接。');
  fs.mkdirSync(path.dirname(file),{recursive:true,mode:0o700});
  const tmp=file+'.'+crypto.randomUUID()+'.tmp';
  try{fs.writeFileSync(tmp,content,{flag:'wx',mode});fs.renameSync(tmp,file);}finally{fs.rmSync(tmp,{force:true});}
}
function execQuote(s){
  if(/[\r\n\0]/.test(s))throw Error('安装路径包含不支持的换行字符。');
  return '"'+s.replace(/(["`$\\])/g,'\\$1').replace(/%/g,'%%')+'"';
}
function desktopEntry(launcher,name,action,terminal){
  return `[Desktop Entry]\nType=Application\nName=${name}\nComment=TokenBots Linux desktop\nExec=${execQuote(launcher)} ${action}\nIcon=chatgpt\nTerminal=${terminal}\nCategories=Development;\nStartupNotify=true\n`;
}
function install(p=paths(),source=__dirname){
  privateDir(p.base);privateDir(p.profile);privateDir(p.ui);
  const payload=['linux.cjs','tokenbots.cjs','tokenbots.sh','platform.sh','packages.tsv','README.txt','THIRD-PARTY-LICENSE.txt','native-menu/tokenbots-images.cjs'];
  const digest=crypto.createHash('sha256');
  for(const file of payload)digest.update(file).update(fs.readFileSync(path.join(source,file)));
  const id=VERSION+'-'+digest.digest('hex').slice(0,12);
  const dir=path.join(p.base,'releases',id);
  if(!fs.existsSync(dir)){
    const staging=dir+'.'+crypto.randomUUID()+'.tmp';privateDir(staging);
    try{
      for(const file of payload)atomic(path.join(staging,file),fs.readFileSync(path.join(source,file)),file.endsWith('.sh')?0o700:0o600);
      fs.renameSync(staging,dir);
    }finally{fs.rmSync(staging,{recursive:true,force:true});}
  }else{
    for(const file of payload)if(!fs.readFileSync(path.join(dir,file)).equals(fs.readFileSync(path.join(source,file))))throw Error('已安装版本内容不一致，请检查安装文件。');
  }
  const current=path.join(p.base,'current');
  if(fs.existsSync(current)&&!fs.lstatSync(current).isSymbolicLink())throw Error('current 路径被其他文件占用。');
  const temp=current+'.'+crypto.randomUUID();fs.symlinkSync(dir,temp);fs.renameSync(temp,current);
  fs.mkdirSync(p.applications,{recursive:true});
  const launcher=path.join(current,'tokenbots.sh');
  for(const [file,name,action,terminal] of [
    ['tokenbots-codex.desktop','TokenBots Codex','start',false],
    ['tokenbots-codex-setup.desktop','TokenBots 登录设置','configure',true],
    ['tokenbots-codex-update.desktop','TokenBots 检查更新','update',true],
    ['tokenbots-codex-usage.desktop','TokenBots 用量查询','usage',true],
  ])atomic(path.join(p.applications,file),desktopEntry(launcher,name,action,terminal));
  cp.spawnSync('update-desktop-database',[p.applications],{stdio:'ignore'});
  atomic(path.join(p.base,'installed.json'),JSON.stringify({version:VERSION,release:id,installedAt:new Date().toISOString()},null,2)+'\n');
  return {version:VERSION,profile:p.profile,launcher};
}
async function configure(key,p=paths(),{origin='https://pilot.tokenbots.top',localTest=false}={}){
  key=key.trim();
  const access=client.validateAccess({public_origin:origin,base_url:origin+'/v1',key,label:'TokenBots'},localTest);
  privateDir(p.base);privateDir(p.profile);
  const af=path.join(p.profile,'auth.json');
  // This is our dedicated profile; never read or overwrite ~/.codex/auth.json.
  const previous=fs.existsSync(af)?fs.readFileSync(af):null;
  const result=await client.configure({home:p.profile,target:'desktop',access,localTest});
  try{
    if(previous)atomic(path.join(p.profile,'.tokenbots-setup',path.basename(result.backup)+'.auth'),previous);
    atomic(af,JSON.stringify({OPENAI_API_KEY:key})+'\n');
  }catch(e){client.rollback(p.profile);throw e;}
  return {configured:true,version:VERSION};
}
function runtime(){
  for(const root of ['/usr/lib/chatgpt','/opt/ChatGPT','/opt/chatgpt']){
    if(fs.existsSync(path.join(root,'resources/codex'))){
      const binary=['chatgpt','ChatGPT','codex-desktop'].map(n=>path.join(root,n)).find(fs.existsSync);
      if(binary)return {root,binary,codex:path.join(root,'resources/codex')};
    }
  }
  throw Error('未找到官方 Linux 客户端，请重新安装。');
}
function launchSpec(p=paths(),r=runtime(),{localTest=false}={}){
  client.validateAccess(JSON.parse(fs.readFileSync(path.join(p.profile,'tokenbots-access.json'),'utf8')),localTest);
  privateDir(p.ui);
  return {command:r.binary,args:['--user-data-dir='+p.ui],env:{...process.env,CODEX_HOME:p.profile,CODEX_ELECTRON_USER_DATA_PATH:p.ui}};
}
async function main(argv=process.argv.slice(2)){
  if(process.platform!=='linux')throw Error('此入口只适用于 Linux。');
  if(process.getuid?.()===0)throw Error('请以桌面用户运行，不要使用 sudo 启动客户端。');
  const [action='start',...args]=argv,p=paths();
  if(action==='install')return console.log(JSON.stringify(install(),null,2));
  if(action==='configure'){
    let input='';for await(const b of process.stdin){input+=b;if(input.length>512)throw Error('API Key 格式不正确。');}
    await configure(input,p);console.log('TokenBots 登录验证通过。请重新打开 TokenBots Codex。');return;
  }
  if(action==='start'){
    if(!fs.existsSync(path.join(p.profile,'tokenbots-access.json'))){
      const text='请先从应用菜单打开“TokenBots 登录设置”，输入你自己的 TokenBots API Key。';
      cp.spawnSync('zenity',['--info','--title=TokenBots','--text='+text],{stdio:'ignore'});throw Error(text);
    }
    if(!process.env.DISPLAY&&!process.env.WAYLAND_DISPLAY)throw Error('未检测到 Linux 桌面。请在桌面会话中打开，终端用户可运行 tokenbots.sh cli。');
    const spec=launchSpec(p),child=cp.spawn(spec.command,[...spec.args,...args],{env:spec.env,stdio:'inherit'});
    child.on('error',()=>{console.error('客户端未能启动。');process.exitCode=1;});child.on('exit',c=>process.exitCode=c??1);return;
  }
  if(action==='cli')return client.main(['run','--target','desktop','--home',p.profile,'--codex',runtime().codex,'--',...args]);
  if(action==='usage')return client.main(['usage','--target','desktop','--home',p.profile,...args]);
  if(action==='doctor'){
    const r=runtime();console.log(JSON.stringify({installer:VERSION,os:os.release(),arch:os.arch(),profile:p.profile,desktop:p.ui,configured:fs.existsSync(path.join(p.profile,'tokenbots-access.json')),cli:cp.execFileSync(r.codex,['--version'],{encoding:'utf8'}).trim()},null,2));return;
  }
  if(action==='record-update'){
    const at=new Date().toISOString();atomic(path.join(p.base,'last-update-check.json'),JSON.stringify({checkedAt:at})+'\n');console.log('检查更新已完成 / Last checked: '+at);return;
  }
  if(action==='uninstall'){
    for(const file of ['tokenbots-codex.desktop','tokenbots-codex-setup.desktop','tokenbots-codex-update.desktop','tokenbots-codex-usage.desktop'])fs.rmSync(path.join(p.applications,file),{force:true});
    console.log('已移除 TokenBots 应用菜单入口。对话、登录和官方客户端均已保留：'+p.base);return;
  }
  throw Error('未知命令。支持 start / configure / cli / usage / doctor / update / uninstall。');
}
module.exports={paths,install,configure,launchSpec,execQuote,desktopEntry,VERSION};
if(require.main===module)main().catch(e=>{console.error(/^Service returned HTTP/.test(e.message)?e.message:/[\u4e00-\u9fff]/.test(e.message)?e.message:'操作失败；请检查网络和 TokenBots API Key。未输出任何凭据。');process.exitCode=1;});
