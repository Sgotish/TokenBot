'use strict';
// Actual official Linux app, synthetic loopback provider, no live customer key.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),http=require('node:http'),net=require('node:net'),cp=require('node:child_process'),assert=require('node:assert/strict');
const {chromium}=require('/usr/lib/chatgpt/resources/cua_node/lib/node_modules/playwright-core');
const linux=require(path.resolve('delivery/linux-2026111601/TokenBots-Linux/linux.cjs'));
fs.mkdirSync('reports',{recursive:true});
const p=linux.paths(),key='fixture_only_no_real_account_123456',requests=[];
const server=http.createServer((req,res)=>{
  let raw='';req.on('data',b=>raw+=b);req.on('end',()=>{
    if(req.headers.authorization!=='Bearer '+key){res.writeHead(401);res.end('{}');return;}
    const body=raw?JSON.parse(raw):null;requests.push({path:req.url,model:body?.model});
    if(req.url==='/v1/models'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({data:require('../integrations/model-catalog/models.json').models}));return;}
    if(req.url==='/v1/responses'){
      res.writeHead(200,{'Content-Type':'text/event-stream'});
      const message={id:'msg_linux',type:'message',role:'assistant',status:'completed',content:[{type:'output_text',text:'Linux install verified: 42',annotations:[]}]};
      const response={id:'resp_linux',object:'response',created_at:1,model:body.model,status:'completed',output:[message],usage:{input_tokens:1,output_tokens:1,total_tokens:2}};
      const events=[{type:'response.created',response:{...response,status:'in_progress',output:[]}},{type:'response.output_item.added',output_index:0,item:{...message,status:'in_progress',content:[]}},{type:'response.content_part.added',item_id:message.id,output_index:0,content_index:0,part:{type:'output_text',text:'',annotations:[]}},{type:'response.output_text.delta',item_id:message.id,output_index:0,content_index:0,delta:message.content[0].text},{type:'response.output_text.done',item_id:message.id,output_index:0,content_index:0,text:message.content[0].text},{type:'response.output_item.done',output_index:0,item:message},{type:'response.completed',response}];
      for(const [i,event]of events.entries())res.write('data: '+JSON.stringify({...event,sequence_number:i})+'\n\n');res.end();return;
    }
    res.writeHead(404);res.end('{}');
  });
});
let app,browser;const output=[];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function open(){
  const listener=net.createServer();await new Promise(r=>listener.listen(0,'127.0.0.1',r));const port=listener.address().port;await new Promise(r=>listener.close(r));
  const spec=linux.launchSpec(p,{binary:'/usr/lib/chatgpt/ChatGPT'},{localTest:true});
  app=cp.spawn(spec.command,[...spec.args,'--remote-debugging-port='+port,'--force-renderer-accessibility'],{env:spec.env,stdio:['ignore','pipe','pipe'],detached:true});
  app.stdout.on('data',b=>output.push(String(b)));app.stderr.on('data',b=>output.push(String(b)));
  for(let attempt=0;attempt<60;attempt++){
    if(app.exitCode!==null)throw Error('Linux desktop exited '+app.exitCode);
    try{browser=await chromium.connectOverCDP('http://127.0.0.1:'+port,{timeout:1000});break;}catch{await sleep(500);}
  }
  if(!browser)throw Error('Native app CDP unavailable');
  await sleep(10000);
  const pages=browser.contexts().flatMap(c=>c.pages());
  assert(pages.length,'No application window');
  const page=pages.find(p=>!p.url().startsWith('devtools:'));
  page.setDefaultTimeout(10000);return page;
}
async function snapshot(page,name){
  await page.screenshot({path:'reports/linux-'+name+'.png'});
  fs.writeFileSync('reports/linux-'+name+'.txt',await page.locator('body').innerText());
  fs.writeFileSync('reports/linux-'+name+'-controls.json',JSON.stringify(await page.locator('input,textarea,[contenteditable=true],button').evaluateAll(nodes=>nodes.map(e=>({tag:e.tagName,role:e.getAttribute('role'),label:e.getAttribute('aria-label'),placeholder:e.getAttribute('placeholder'),text:e.textContent?.slice(0,100)}))),null,2));
}
async function close(){
  if(browser){await browser.close();browser=null;}
  if(app){try{process.kill(-app.pid,'SIGTERM');}catch{}await Promise.race([new Promise(r=>app.once('exit',r)),sleep(5000)]);try{process.kill(-app.pid,'SIGKILL');}catch{}}
}
async function quitNormally(page){
  // Use the app's observed Linux Quit accelerator, so its app-server can flush
  // the rollout before exit. SIGKILL below is cleanup only, not restart testing.
  const exited=new Promise(resolve=>app.once('exit',resolve));
  // CDP keyboard events do not invoke this app's native menu accelerators.
  // Deliver Ctrl+Q through the disposable Linux test desktop's X server.
  const window=cp.execFileSync('xdotool',['search','--onlyvisible','--pid',String(app.pid)],{encoding:'utf8'}).trim().split('\n')[0];
  assert(window,'No visible native window to quit');
  cp.execFileSync('xdotool',['windowfocus','--sync',window]);
  cp.execFileSync('xdotool',['key','--clearmodifiers','ctrl+q']);
  await Promise.race([exited,sleep(20000).then(()=>{if(app.exitCode===null)throw Error('Official Quit did not exit');})]);
  if(browser){await browser.close().catch(()=>{});browser=null;}
}
async function main(){
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  await linux.configure(key,p,{origin:'http://127.0.0.1:'+server.address().port,localTest:true});
  // Use the app's real CLI to create and persist a synthetic conversation.
  const cli='/usr/lib/chatgpt/resources/codex';
  const args=['exec','--skip-git-repo-check','--sandbox','read-only','-m','gpt-6.1-sol','-c','model_reasoning_effort="low"','--json','Linux installer conversation sentinel. Reply only 42; do not use tools.'];
  const run=cp.spawn(cli,args,{env:{...process.env,CODEX_HOME:p.profile},stdio:['ignore','pipe','pipe'],timeout:90000});let stdout='',stderr='';
  run.stdout.on('data',b=>stdout+=b);run.stderr.on('data',b=>stderr+=b);
  const code=await new Promise((r,j)=>{run.on('error',j);run.on('exit',r);});
  assert.equal(code,0,stderr.replaceAll(key,'[redacted]'));assert(stdout.includes('Linux install verified: 42'));
  const events=stdout.trim().split('\n').map(l=>JSON.parse(l));
  const threadId=events.find(e=>e.type==='thread.started')?.thread_id;assert(threadId,'No real persisted thread id');
  const config=path.join(p.profile,'config.toml');fs.writeFileSync(config,fs.readFileSync(config,'utf8').replace(/^model = .+$/m,'model = "gpt-6.1-sol"').replace(/^model_reasoning_effort = .+$/m,'model_reasoning_effort = "low"'));
  fs.writeFileSync(path.join(p.profile,'.codex-global-state.json'),JSON.stringify({'electron-persisted-atom-state':{'electron:onboarding-projectless-completed':true}}));
  let page=await open();await snapshot(page,'first-start');
  const engineering=page.getByRole('button',{name:'Engineering',exact:true});
  if(await engineering.isVisible()){await engineering.click();await page.getByRole('button',{name:'Continue',exact:true}).click();await sleep(3000);}
  await snapshot(page,'ready');
  const text=await page.locator('body').innerText();assert(!/Log in to ChatGPT|Sign in to ChatGPT/.test(text),'API key did not reach desktop');
  assert(/New (chat|thread)|Plugins|Skills|Codex/i.test(text),'No recognizable native workspace');
  const editor=page.locator('[contenteditable=true]').first();
  await editor.fill('Linux desktop acceptance sentinel. Reply only 42; do not use tools.');
  await editor.press('Enter');
  await page.getByText('Linux install verified: 42',{exact:true}).waitFor({timeout:30000});
  await page.getByRole('button',{name:'Send',exact:true}).waitFor({timeout:15000});
  await snapshot(page,'desktop-response');
  await quitNormally(page);
  const authBefore=fs.readFileSync(path.join(p.profile,'auth.json'));
  linux.install(p,path.resolve('delivery/linux-2026111601/TokenBots-Linux'));
  assert(fs.readFileSync(path.join(p.profile,'auth.json')).equals(authBefore));
  page=await open();await snapshot(page,'after-reinstall');
  if(!((await page.locator('body').innerText()).includes('Linux install verified: 42'))){
    const recent=page.getByText(/Linux desktop acceptance sentinel/).first();
    // The title overflows under the hover-only pin/archive controls. Its visual
    // center can hit Pin instead of opening the chat; click the visible text.
    await recent.click({position:{x:8,y:8}});
    await page.getByText('Linux install verified: 42',{exact:true}).waitFor({timeout:15000});
  }
  await snapshot(page,'restored-desktop-chat');
  // Query the official app-server after restart to prove actual persisted data,
  // not just a sentinel text file or an HTTP health check.
  const rpc=cp.spawn(cli,['app-server'],{env:{...process.env,CODEX_HOME:p.profile},stdio:['pipe','pipe','pipe']});rpc.stderr.resume();
  let buffer='';const result=await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error('History read timeout')),15000);
    rpc.on('error',reject);rpc.stdout.on('data',b=>{buffer+=b;let n;while((n=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,n);buffer=buffer.slice(n+1);if(!line)continue;const event=JSON.parse(line);
      if(event.id===1){rpc.stdin.write(JSON.stringify({method:'initialized'})+'\n');rpc.stdin.write(JSON.stringify({id:2,method:'thread/read',params:{threadId,includeTurns:true}})+'\n');}
      if(event.id===2){clearTimeout(timer);resolve(event);}
    }});rpc.stdin.write(JSON.stringify({id:1,method:'initialize',params:{clientInfo:{name:'linux-acceptance',version:'1'}}})+'\n');
  });rpc.kill();assert(!result.error,JSON.stringify(result.error));assert(JSON.stringify(result.result).includes('Linux install verified: 42'));
  fs.writeFileSync('reports/linux-acceptance.json',JSON.stringify({installer:linux.VERSION,platform:process.platform,architecture:process.arch,officialCli:cp.execFileSync(cli,['--version'],{encoding:'utf8'}).trim(),nativeWindowOpened:true,apiKeyProfile:true,syntheticResponseCompleted:true,nativeChatSubmitted:true,nativeChatRestored:true,reinstallPreservedAuth:true,restartedHistoryRead:true,liveInference:false,customerMachine:false,requests},null,2));
  console.log('PASS native Linux desktop, synthetic response, auth and real thread history after restart/reinstall');
}
main().catch(async e=>{
  console.error(e);process.exitCode=1;
  if(browser){const page=browser.contexts().flatMap(c=>c.pages())[0];if(page)await snapshot(page,'failure').catch(()=>{});}
}).finally(async()=>{
  await close();server.close();fs.writeFileSync('reports/linux-process.txt',output.join('').replaceAll(key,'[redacted]'));
});
