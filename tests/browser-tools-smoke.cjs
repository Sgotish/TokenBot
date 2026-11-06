// Real MCP + real browser + local fixture. No account, model call or external mutation.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),http=require('node:http');
const {spawn}=require('node:child_process'),readline=require('node:readline'),assert=require('node:assert/strict');
const {install}=require('../integrations/windows-codex/browser-tools/install.cjs');
const home=process.argv[2] || fs.mkdtempSync(path.join(os.tmpdir(),'tb-browser-smoke-'));
let server,child; const pending=new Map();let seq=0;
const timer=setTimeout(()=>{console.error('Browser acceptance timeout');child?.kill();server?.close();process.exit(1);},60000);
async function main(){
 fs.mkdirSync(home,{recursive:true});
 if(!fs.existsSync(path.join(home,'config.toml')))fs.writeFileSync(path.join(home,'config.toml'),'model="gpt-6-astra"\n');
 if(process.argv[3]!=='--installed')install(home,process.execPath);
 const cfg=require('../integrations/windows-codex/browser-tools/node_modules/@iarna/toml').parse(fs.readFileSync(path.join(home,'config.toml'),'utf8')).mcp_servers.tokenbots_browser;
 server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end('<title>TokenBots browser acceptance</title><h1>Ready</h1><button onclick="document.querySelector(\'h1\').textContent=\'Click verified\'">Verify click</button>');});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 child=spawn(cfg.command,cfg.args,{stdio:['pipe','pipe','pipe'],cwd:home});
 let errors='';child.stderr.on('data',d=>errors+=d.toString());
 child.on('error',e=>{for(const p of pending.values())p.reject(e);});
 child.on('exit',code=>{for(const p of pending.values())p.reject(Error('MCP exited '+code+': '+errors.slice(-500)));});
 readline.createInterface({input:child.stdout}).on('line',line=>{try {const msg=JSON.parse(line),p=pending.get(msg.id);if(p){pending.delete(msg.id);msg.error?p.reject(Error(JSON.stringify(msg.error))):p.resolve(msg.result);}}catch{}});
 const rpc=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});child.stdin.write(JSON.stringify({jsonrpc:'2.0',id,method,params})+'\n');});
 await rpc('initialize',{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'TokenBots acceptance',version:'1'}});
 child.stdin.write(JSON.stringify({jsonrpc:'2.0',method:'notifications/initialized'})+'\n');
 const list=await rpc('tools/list'); assert.ok(list.tools.some(t=>t.name==='browser_click'));
 const tool=async(name,args={})=>{const r=await rpc('tools/call',{name,arguments:args});if(r.isError)throw Error(JSON.stringify(r.content));let text=r.content.filter(c=>c.type==='text').map(c=>c.text).join('\n');const link=/\[Snapshot\]\(([^)]+)\)/.exec(text);if(link){const file=path.resolve(home,link[1]);assert.ok(file.startsWith(home+path.sep));text+='\n'+fs.readFileSync(file,'utf8');}return text;};
 const snapshot=await tool('browser_navigate',{url:'http://127.0.0.1:'+server.address().port});
 const ref=/button "Verify click" \[ref=([^\]]+)\]/.exec(snapshot)?.[1];assert.ok(ref,'Button reference missing: '+snapshot);
 const click=list.tools.find(t=>t.name==='browser_click');
 const clickArgs=click.inputSchema.properties.target?{target:ref}:{ref,element:'Verify click'};
 await tool('browser_click',clickArgs);
 const after=await tool('browser_snapshot');assert.match(after,/heading "Click verified"/);
 await tool('browser_close');
 console.log(JSON.stringify({platform:process.platform,registered:true,toolList:true,navigate:true,click:true,changedSnapshot:true,customerDevice:false,externalLogin:false}));
}
main().catch(e=>{console.error(e.message);process.exitCode=1;}).finally(()=>{clearTimeout(timer);child?.stdin.end();child?.kill();server?.close();if(!process.argv[2])fs.rmSync(home,{recursive:true,force:true,maxRetries:5,retryDelay:300});});
