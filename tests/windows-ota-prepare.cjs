const fs=require('node:fs'),path=require('node:path');
const [updater,dir,release]=process.argv.slice(2);
if(updater==='extract'){
 const r=require('../integrations/windows-codex/native-menu/ota-client.cjs').verify(fs.readFileSync(dir));
 for(const f of r.files)fs.writeFileSync(path.join(release,f.name),Buffer.from(f.data,'base64'));
}else require(updater).prepare(dir,fs.readFileSync(release)).catch(e=>{console.error(e.message);process.exitCode=1;});
