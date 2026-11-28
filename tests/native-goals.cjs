const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),cp=require('node:child_process');
const home=fs.mkdtempSync(path.join(os.tmpdir(),'tokenbots-goals-'));
fs.writeFileSync(path.join(home,'config.toml'),'model="gpt-6.1-sol"\nmodel_provider="tokenbots_test"\n[model_providers.tokenbots_test]\nname="TokenBots synthetic"\nbase_url="http://127.0.0.1:9/v1"\nwire_api="responses"\nexperimental_bearer_token="synthetic-no-live-access"\nrequires_openai_auth=false\n');
if(!process.argv[2])throw Error('Pass the official CLI executable path');
const child=cp.spawn(process.argv[2],['app-server'],{cwd:home,env:{...process.env,CODEX_HOME:home},stdio:['pipe','pipe','pipe']});child.stderr.resume();
let id=0,buffer='';const pending=new Map();const rpc=(method,params)=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});child.stdin.write(JSON.stringify({id:n,method,params})+'\n');});
child.stdout.on('data',v=>{buffer+=v;let n;while((n=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,n);buffer=buffer.slice(n+1);if(!line)continue;const d=JSON.parse(line);if(pending.has(d.id)){const p=pending.get(d.id);pending.delete(d.id);d.error?p.reject(Error(JSON.stringify(d.error))):p.resolve(d.result);}}});
const timeout=setTimeout(()=>{child.kill();process.exitCode=1},20000);
(async()=>{try{
await rpc('initialize',{clientInfo:{name:'tokenbots-goals-verification',version:'1'},capabilities:{experimentalApi:true}});child.stdin.write('{"method":"initialized"}\n');
const started=await rpc('thread/start',{cwd:home,model:'gpt-6.1-sol',modelProvider:'tokenbots_test',approvalPolicy:'never',sandbox:'read-only'});
const threadId=started.thread.id;
await rpc('thread/goal/set',{threadId,objective:'Synthetic long-running goal; leave paused.',status:'paused',origin:'user'});
const goal=await rpc('thread/goal/get',{threadId});require('node:assert/strict').equal(goal.goal.status,'paused');require('node:assert/strict').equal(goal.goal.tokensUsed,0);console.log('PASS: native API-key profile can create and read a paused long-running goal without inference.');
await rpc('thread/goal/clear',{threadId});require('node:assert/strict').equal((await rpc('thread/goal/get',{threadId})).goal,null);console.log('PASS: synthetic goal cleared.');
}catch(e){console.error(e.message);process.exitCode=1}finally{clearTimeout(timeout);child.kill();await new Promise(r=>child.on('close',r));fs.rmSync(home,{recursive:true,force:true});}})();
