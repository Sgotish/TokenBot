'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),http=require('node:http'),cp=require('node:child_process');
const {parse}=require('smol-toml');
const client=require('./client.cjs');
const key='fixture_only_not_a_real_key_12345';
async function fixture(t){
 const requests=[];
 const server=http.createServer((req,res)=>{
  let raw='';req.on('data',b=>raw+=b);req.on('end',()=>{
  const body=raw?JSON.parse(raw):null;requests.push({path:req.url,auth:req.headers.authorization,body});
  if(req.headers.authorization!=='Bearer '+key){res.writeHead(401);res.end('{}');return;}
  if(req.url==='/v1/models'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({data:require('../model-catalog/models.json').models}));return;}
  if(req.url.startsWith('/v1/responses')){
   res.writeHead(200,{'Content-Type':'text/event-stream'});
   if(body.input?.some(item=>item.type==='compaction_trigger')){
    const item={id:'cmp_fixture',type:'compaction',encrypted_content:'opaque_fixture_only'};
    res.write('data: '+JSON.stringify({type:'response.output_item.done',sequence_number:0,output_index:0,item})+'\n\n');
    res.end('data: '+JSON.stringify({type:'response.completed',sequence_number:1,response:{id:'resp_compact',object:'response',model:body.model,status:'completed',output:[item],usage:{input_tokens:10,output_tokens:5,total_tokens:15}}})+'\n\n');return;
   }
   const message={id:'msg_fixture',type:'message',role:'assistant',status:'completed',content:[{type:'output_text',text:'42',annotations:[]}]};
   const response={id:'resp_fixture',object:'response',created_at:1,model:body.model,status:'completed',output:[message],usage:{input_tokens:1,output_tokens:1,total_tokens:2}};
   const events=[{type:'response.created',response:{...response,status:'in_progress',output:[]}},{type:'response.output_item.added',output_index:0,item:{...message,status:'in_progress',content:[]}},{type:'response.content_part.added',item_id:message.id,output_index:0,content_index:0,part:{type:'output_text',text:'',annotations:[]}},{type:'response.output_text.delta',item_id:message.id,output_index:0,content_index:0,delta:'42'},{type:'response.output_text.done',item_id:message.id,output_index:0,content_index:0,text:'42'},{type:'response.output_item.done',output_index:0,item:message},{type:'response.completed',response}];
   for(const [i,e]of events.entries())res.write('data: '+JSON.stringify({...e,sequence_number:i})+'\n\n');res.end();return;
  }
  res.writeHead(404);res.end('{}');
  });
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));t.after(()=>server.close());
 const origin='http://127.0.0.1:'+server.address().port;
 const home=fs.mkdtempSync(path.join(os.tmpdir(),'TokenBots space 测试-'));
 // Windows may retain handles briefly after the npm wrapper exits. Await all
 // child stdio below, then retry cleanup for a bounded period; never hide errors.
 t.after(()=>fs.promises.rm(home,{recursive:true,force:true,maxRetries:20,retryDelay:100}));
 return {home,requests,access:{public_origin:origin,base_url:origin+'/v1',key},target:'cli',localTest:true};
}
test('configure, update and rollback preserve unrelated config and original bytes',async t=>{
 const f=await fixture(t),file=path.join(f.home,'config.toml');
 const original='# comment\nmodel="old"\n[mcp_servers.demo]\ncommand="node"\nargs=["hello world"]\n[permissions.private]\nnetwork="deny"\n';fs.writeFileSync(file,original);
 await client.configure(f);let data=parse(fs.readFileSync(file,'utf8'));
 assert.equal(data.mcp_servers.demo.args[0],'hello world');assert.equal(data.permissions.private.network,'deny');
 assert.equal(data.model_providers[client.PROVIDER].env_key,'TOKENBOTS_API_KEY');assert.ok(!fs.readFileSync(file,'utf8').includes(key));
 assert.equal(data.model_providers[client.PROVIDER].capabilities.remote_compaction,'v2');
 const first=fs.readFileSync(file,'utf8');await new Promise(r=>setTimeout(r,2));
 await client.configure({...f,target:'desktop'});data=parse(fs.readFileSync(file,'utf8'));
 assert.equal(data.model_providers[client.PROVIDER].experimental_bearer_token,key);
 client.rollback(f.home);assert.equal(fs.readFileSync(file,'utf8'),first);
 client.rollback(f.home);assert.equal(fs.readFileSync(file,'utf8'),original);assert.ok(!fs.existsSync(path.join(f.home,'tokenbots-access.json')));
});
test('failed credentials and invalid TOML never alter configuration',async t=>{
 const f=await fixture(t),file=path.join(f.home,'config.toml');fs.writeFileSync(file,'model = "old"\n');
 await assert.rejects(client.configure({...f,access:{...f.access,key:'wrong_key_1234567890'}}),/HTTP 401/);
 assert.equal(fs.readFileSync(file,'utf8'),'model = "old"\n');
 fs.writeFileSync(file,'invalid="secret');await assert.rejects(client.configure(f),/Invalid existing TOML/);
 assert.equal(fs.readFileSync(file,'utf8'),'invalid="secret');
});
test('rollback refuses overwriting changes made after setup',async t=>{
 const f=await fixture(t);await client.configure(f);fs.appendFileSync(path.join(f.home,'config.toml'),'\n# new preference\n');
 assert.throws(()=>client.rollback(f.home),/Configuration changed/);
});
test('active profile preserves its permissions and settings without overriding the new provider',async t=>{
 const f=await fixture(t),file=path.join(f.home,'config.toml');
 const original='profile="work"\nmodel="old"\n[features]\na=true\n';
 const profile='model_provider="old_proxy"\napproval_policy="on-request"\n[features]\nb=true\n';
 fs.writeFileSync(file,original);fs.writeFileSync(path.join(f.home,'work.config.toml'),profile);
 await client.configure(f);const d=parse(fs.readFileSync(file,'utf8'));
 assert.equal(d.profile,undefined);assert.equal(d.approval_policy,'on-request');assert.deepEqual({...d.features},{a:true,b:true});assert.equal(d.model_provider,client.PROVIDER);
 assert.equal(fs.readFileSync(path.join(f.home,'work.config.toml'),'utf8'),profile);
 client.rollback(f.home);assert.equal(fs.readFileSync(file,'utf8'),original);
});
test('reject insecure origins, embedded credentials and redirect before token forwarding',async t=>{
 const f=await fixture(t);assert.throws(()=>client.validateAccess(f.access));
 assert.throws(()=>client.validateAccess({...f.access,public_origin:'https://user:pass@example.com',base_url:'https://user:pass@example.com/v1'}));
 const redirect=http.createServer((req,res)=>{res.writeHead(302,{Location:f.access.public_origin+'/v1/models'});res.end();});
 await new Promise(r=>redirect.listen(0,'127.0.0.1',r));t.after(()=>redirect.close());
 await assert.rejects(client.request({...f.access,public_origin:'http://127.0.0.1:'+redirect.address().port},'/v1/models'));
 assert.equal(f.requests.length,0);
});
test('usage distinguishes unknown and stale; SSE probe needs completed answer',async t=>{
 const f=await fixture(t);assert.equal((await client.probe(f.access)).answer,'42');
 assert.match(client.displayUsage({accounts:[{label:'Pro',windows:[{label:'5h',remaining_percent:null},{label:'7d',remaining_percent:80,stale:true}]}]}),/unknown/);
 assert.match(client.displayUsage({accounts:[{label:'Pro',windows:[{remaining_percent:80,stale:true}]}]}),/80% \[stale\]/);
});
test('real installed Codex CLI consumes generated config and completes a streamed turn',{skip:process.env.RUN_CODEX_SMOKE!=='1',timeout:90000},async t=>{
 const f=await fixture(t);await client.configure(f);
 const bin=client.resolveCodex(process.env.TOKENBOTS_TEST_CODEX);
 const out=path.join(f.home,'answer.txt');
 const args=[...bin.args,'exec','--skip-git-repo-check','--ephemeral','--sandbox','read-only','-c','model_reasoning_effort="low"','--output-last-message',out,'Reply with 42 only. Do not use tools.'];
 let stderr='';const proc=cp.spawn(bin.command,args,{cwd:f.home,env:{...process.env,CODEX_HOME:f.home,TOKENBOTS_API_KEY:key},stdio:['ignore','pipe','pipe']});
 proc.stdout.resume();proc.stderr.on('data',b=>stderr+=b);t.after(()=>proc.kill());
 const code=await new Promise((resolve,reject)=>{proc.on('error',reject);proc.on('close',resolve);});
 assert.equal(code,0,stderr.replaceAll(key,'[redacted]'));assert.equal(fs.readFileSync(out,'utf8').trim(),'42');
 assert.ok(f.requests.some(r=>r.path.includes('/responses')&&r.auth==='Bearer '+key&&r.body.model==='gpt-6-astra'&&r.body.reasoning.effort==='low'));
});

test('setup preserves a supported selected model and effort',async t=>{
 const f=await fixture(t),file=path.join(f.home,'config.toml');
 fs.writeFileSync(file,'model="gpt-6-astra"\nmodel_reasoning_effort="xhigh"\n');
 await client.configure(f);const d=parse(fs.readFileSync(file,'utf8'));
 assert.equal(d.model,'gpt-6-astra');assert.equal(d.model_reasoning_effort,'xhigh');
});
test('actual Codex compacts and resumes with opaque state',{skip:process.env.RUN_CODEX_SMOKE!=='1',timeout:30000},async t=>{
 const f=await fixture(t);await client.configure(f);const bin=client.resolveCodex(process.env.TOKENBOTS_TEST_CODEX);
 const proc=cp.spawn(bin.command,[...bin.args,'app-server'],{cwd:f.home,env:{...process.env,CODEX_HOME:f.home,TOKENBOTS_API_KEY:key},stdio:['pipe','pipe','pipe']});
 t.after(()=>proc.kill());proc.stderr.resume();let next=0,raw='';const pending=new Map(),notes=[],waiters=[];
 const rpc=(method,params)=>new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});proc.stdin.write(JSON.stringify({id,method,params})+'\n');});
 const completed=()=>{const count=notes.filter(n=>n.method==='turn/completed').length;return new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('No completed turn after compaction')),10000);
  waiters.push(()=>{if(notes.filter(n=>n.method==='turn/completed').length>count){clearTimeout(timer);resolve();return true;}});
 });};
 proc.stdout.on('data',b=>{raw+=b;let split;while((split=raw.indexOf('\n'))>=0){const line=raw.slice(0,split);raw=raw.slice(split+1);if(!line)continue;const d=JSON.parse(line);
  if(pending.has(d.id)){const p=pending.get(d.id);pending.delete(d.id);d.error?p.reject(Error(JSON.stringify(d.error))):p.resolve(d.result);}
  else{notes.push(d);for(let i=waiters.length-1;i>=0;i--)if(waiters[i]())waiters.splice(i,1);}
 }});
 await rpc('initialize',{clientInfo:{name:'tokenbots-compact-test',version:'1'},capabilities:{experimentalApi:true}});
 proc.stdin.write(JSON.stringify({method:'initialized'})+'\n');
 const thread=await rpc('thread/start',{cwd:f.home,model:'gpt-6.1-sol',modelProvider:client.PROVIDER,approvalPolicy:'never',sandbox:'read-only',ephemeral:true});
 let done=completed();await rpc('turn/start',{threadId:thread.thread.id,input:[{type:'text',text:'Remember synthetic Cedar42.',text_elements:[]}]});await done;
 done=completed();await rpc('thread/compact/start',{threadId:thread.thread.id});await done;
 assert(f.requests.some(r=>r.body?.input?.some(i=>i.type==='compaction_trigger')));
 done=completed();await rpc('turn/start',{threadId:thread.thread.id,input:[{type:'text',text:'Continue the synthetic project.',text_elements:[]}]});await done;
 const last=f.requests.filter(r=>r.path==='/v1/responses').at(-1);
 assert(last.body.input.some(i=>i.type==='compaction'&&i.encrypted_content==='opaque_fixture_only'));
 assert(!notes.some(n=>n.method==='turn/completed'&&n.params.turn.status==='failed'));
 const closed=new Promise(r=>proc.on('close',r));proc.kill();await closed;
});
test('actual app-server exposes all seven models and supported efforts',{skip:process.env.RUN_CODEX_SMOKE!=='1',timeout:30000},async t=>{
 const f=await fixture(t);await client.configure(f);const bin=client.resolveCodex(process.env.TOKENBOTS_TEST_CODEX);
 const proc=cp.spawn(bin.command,[...bin.args,'app-server'],{env:{...process.env,CODEX_HOME:f.home,TOKENBOTS_API_KEY:key},stdio:['pipe','pipe','pipe']});
 t.after(()=>proc.kill());proc.stderr.resume();
 const send=x=>proc.stdin.write(JSON.stringify(x)+'\n');
 const result=await new Promise((resolve,reject)=>{let raw='';
  proc.on('error',reject);proc.on('exit',()=>reject(Error('App server exited before listing models')));
  proc.stdout.on('data',b=>{raw+=b;let split;while((split=raw.indexOf('\n'))>=0){const line=raw.slice(0,split);raw=raw.slice(split+1);if(!line)continue;const d=JSON.parse(line);
   if(d.id===1){send({method:'initialized'});send({id:2,method:'model/list',params:{includeHidden:false}});}
   if(d.id===2)resolve(d);
  }});
  send({id:1,method:'initialize',params:{clientInfo:{name:'tokenbots-test',version:'1'},capabilities:{experimentalApi:true}}});
 });
 assert(!result.error,JSON.stringify(result.error));
 for(const expected of require('../model-catalog/models.json').models){
  const m=result.result.data.find(m=>m.id===expected.id);assert(m,expected.id);
  for(const e of expected.reasoning_efforts)assert(m.supportedReasoningEfforts.some(x=>x.reasoningEffort===e),expected.id+':'+e);
 }
 const closed=new Promise(r=>proc.on('close',r));proc.kill();await closed;
});
test('actual CLI translates Ultra client mode before sending the upstream request',{skip:process.env.RUN_CODEX_SMOKE!=='1',timeout:90000},async t=>{
 const f=await fixture(t);await client.configure(f);const bin=client.resolveCodex(process.env.TOKENBOTS_TEST_CODEX);
 const out=path.join(f.home,'ultra-answer.txt');
 const proc=cp.spawn(bin.command,[...bin.args,'exec','--skip-git-repo-check','--ephemeral','--sandbox','read-only','-c','model_reasoning_effort="ultra"','--output-last-message',out,'Reply with 42 only. Do not use tools or delegate.'],{cwd:f.home,env:{...process.env,CODEX_HOME:f.home,TOKENBOTS_API_KEY:key},stdio:['ignore','pipe','pipe']});
 let err='';proc.stdout.resume();proc.stderr.on('data',b=>err+=b);t.after(()=>proc.kill());
 const code=await new Promise((r,j)=>{proc.on('error',j);proc.on('close',r);});
 assert.equal(code,0,err.replaceAll(key,'[redacted]'));assert.equal(fs.readFileSync(out,'utf8').trim(),'42');
 const sent=f.requests.find(r=>r.path.includes('/responses'));
 assert(sent);assert.notEqual(sent.body.reasoning.effort,'ultra');
 assert(['max','xhigh'].includes(sent.body.reasoning.effort));
 console.log('Ultra upstream effort:',sent.body.reasoning.effort);
});
test('each model can be selected by actual CLI without model or effort fallback',{skip:process.env.RUN_CODEX_SMOKE!=='1',timeout:90000},async t=>{
 const f=await fixture(t);await client.configure(f);const bin=client.resolveCodex(process.env.TOKENBOTS_TEST_CODEX);
 for(const model of require('../model-catalog/models.json').models){
  const first=f.requests.length;
  const proc=cp.spawn(bin.command,[...bin.args,'exec','--skip-git-repo-check','--ephemeral','--sandbox','read-only','-m',model.id,'-c','model_reasoning_effort="high"','Reply only 42. Do not use tools.'],{cwd:f.home,env:{...process.env,CODEX_HOME:f.home,TOKENBOTS_API_KEY:key},stdio:['ignore','pipe','pipe']});
  let err='';proc.stdout.resume();proc.stderr.on('data',b=>err+=b);t.after(()=>proc.kill());
  const code=await new Promise((r,j)=>{proc.on('error',j);proc.on('close',r);});assert.equal(code,0,err.replaceAll(key,'[redacted]'));
  const sent=f.requests.slice(first).find(r=>r.path.includes('/responses'));assert(sent,model.id);
  assert.equal(sent.body.model,model.id);assert.equal(sent.body.reasoning.effort,'high');
  assert([undefined,'auto','default'].includes(sent.body.service_tier),model.id+':'+sent.body.service_tier);
 }
});
