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
  for(const name of ['package-lock.json','browser.cjs','desktop.cjs','desktop.ps1'])digest.update(fs.readFileSync(path.join(source,name)));
  const version=digest.digest('hex').slice(0,16);
  const target=path.join(home,'tools','tokenbots-browser-'+version);
  fs.mkdirSync(path.dirname(target),{recursive:true});
  // Repair an interrupted/stale copy; config is changed only after this succeeds.
  fs.cpSync(source,target,{recursive:true,filter:p=>!p.split(path.sep).includes('.bin')});
  const block='[mcp_servers.tokenbots_browser]\ncommand = '+JSON.stringify(node)+'\nargs = '+JSON.stringify([path.join(target,'browser.cjs'),home])+'\nstartup_timeout_sec = 30\ntool_timeout_sec = 90\n';
  const pattern=/^\[mcp_servers\.tokenbots_browser\][ \t]*\r?\n(?:(?!^[ \t]*\[)[\s\S])*/gm;
  const matches=[...original.matchAll(pattern)];
  if(matches.length>1 || (before.mcp_servers?.tokenbots_browser && matches.length!==1))throw Error('Unsupported existing browser table; config unchanged');
  let updated=matches.length?original.replace(pattern,()=>block):original.trimEnd()+'\n\n'+block;
  const desktopBlock='[mcp_servers.tokenbots_desktop]\ncommand = '+JSON.stringify(node)+'\nargs = '+JSON.stringify([path.join(target,'desktop.cjs')])+'\nstartup_timeout_sec = 30\ntool_timeout_sec = 90\n';
  const desktopPattern=/^\[mcp_servers\.tokenbots_desktop\][ \t]*\r?\n(?:(?!^[ \t]*\[)[\s\S])*/gm;
  const desktopMatches=[...updated.matchAll(desktopPattern)];
  if(desktopMatches.length>1 || (before.mcp_servers?.tokenbots_desktop && desktopMatches.length!==1))throw Error('Unsupported existing desktop table; config unchanged');
  updated=desktopMatches.length?updated.replace(desktopPattern,()=>desktopBlock):updated.trimEnd()+'\n'+desktopBlock;
  // Remove our obsolete zero-retry trial overrides; the Codex defaults apply.
  updated=updated.replace(/(^\[model_providers\.tokenbots_partner_20261016\][ \t]*\r?\n)(?:(?!^[ \t]*\[)[\s\S])*/gm,part=>part.replace(/^(request_max_retries|stream_max_retries)[ \t]*=[ \t]*0[ \t]*\r?\n/gm,''));
  const caps='[model_providers.tokenbots_partner_20261016.capabilities]';
  if(before.model_providers?.tokenbots_partner_20261016) {
    const cp=/^\[model_providers\.tokenbots_partner_20261016\.capabilities\][ \t]*\r?\n(?:(?!^[ \t]*\[)[\s\S])*/gm;
    const cm=[...updated.matchAll(cp)];if(cm.length>1)throw Error('Ambiguous capabilities');
    updated=cm.length?updated.replace(cp,part=>part.replace(/^remote_compaction[ \t]*=[^\r\n]*\r?\n/gm,'').trimEnd()+'\nremote_compaction = "v2"\n'):updated.trimEnd()+'\n'+caps+'\nremote_compaction = "v2"\n';
  }
  toml.parse(updated);
  // Retire our extra trial workflow prompts; leave customer-created skills alone.
  for(const name of ['tokenbots-browser-check','tokenbots-project-checkpoints']) {
    const dest=path.join(home,'skills',name);
    if(fs.existsSync(path.join(dest,'.tokenbots-owned')))fs.rmSync(dest,{recursive:true,force:true});
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
