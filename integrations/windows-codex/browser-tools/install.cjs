'use strict';
// Installs only the owned MCP table and skills into the selected native home.
const fs=require('node:fs'), path=require('node:path'), crypto=require('node:crypto');
const toml=require('@iarna/toml');
function install(home,node,source=__dirname) {
  const file=path.join(home,'config.toml');
  const original=fs.readFileSync(file,'utf8');
  const before=toml.parse(original);
  if(!fs.existsSync(node)) throw Error('Node runtime missing');
  const digest=crypto.createHash('sha256');
  for(const name of ['package-lock.json','browser.cjs'])digest.update(fs.readFileSync(path.join(source,name)));
  const version=digest.digest('hex').slice(0,16);
  const target=path.join(home,'tools','tokenbots-browser-'+version);
  fs.mkdirSync(path.dirname(target),{recursive:true});
  // Repair an interrupted/stale copy; config is changed only after this succeeds.
  fs.cpSync(source,target,{recursive:true,filter:p=>!p.split(path.sep).includes('.bin')});
  const block='[mcp_servers.tokenbots_browser]\ncommand = '+JSON.stringify(node)+'\nargs = '+JSON.stringify([path.join(target,'browser.cjs'),home])+'\nstartup_timeout_sec = 30\ntool_timeout_sec = 90\n';
  const pattern=/^\[mcp_servers\.tokenbots_browser\][ \t]*\r?\n(?:(?!^[ \t]*\[)[\s\S])*/gm;
  const matches=[...original.matchAll(pattern)];
  if(matches.length>1 || (before.mcp_servers?.tokenbots_browser && matches.length!==1))throw Error('Unsupported existing browser table; config unchanged');
  const updated=matches.length?original.replace(pattern,()=>block):original.trimEnd()+'\n\n'+block;
  toml.parse(updated);
  // Skills are independent of provider/model/auth and do not modify AGENTS.md.
  const skills=path.join(home,'skills'); fs.mkdirSync(skills,{recursive:true});
  for(const name of fs.readdirSync(path.join(source,'skills'))) {
    const dest=path.join(skills,name);
    if(fs.existsSync(dest) && !fs.existsSync(path.join(dest,'.tokenbots-owned')))throw Error('A user-owned skill conflicts: '+name);
  }
  for(const name of fs.readdirSync(path.join(source,'skills'))) {
    const dest=path.join(skills,name);
    fs.cpSync(path.join(source,'skills',name),dest,{recursive:true});
    fs.writeFileSync(path.join(dest,'.tokenbots-owned'),'1\n');
  }
  if(updated!==original) {
    const suffix=crypto.randomUUID(), temp=file+'.tmp-'+suffix;
    fs.writeFileSync(file+'.before-browser-'+suffix,original,{flag:'wx',mode:0o600});
    try { fs.writeFileSync(temp,updated,{flag:'wx',mode:0o600}); fs.renameSync(temp,file); }
    finally { fs.rmSync(temp,{force:true}); }
  }
  return {version,registered:true,deviceAcceptance:'pending'};
}
module.exports={install};
if(require.main===module)try { console.log(JSON.stringify(install(process.argv[2],process.argv[3]))); }
catch(e) { console.error(e.message); process.exitCode=1; }
