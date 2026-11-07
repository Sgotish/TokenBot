'use strict';
// Local foreground Windows UI adapter. Does not read browser profiles or cookies.
const {Server}=require('@modelcontextprotocol/sdk/server/index.js');
const {StdioServerTransport}=require('@modelcontextprotocol/sdk/server/stdio.js');
const {ListToolsRequestSchema,CallToolRequestSchema}=require('@modelcontextprotocol/sdk/types.js');
const {spawn}=require('node:child_process');
const path=require('node:path');
const actions=['observe','focus','click','type','key','scroll'];
function invoke(args){
 if(process.platform!=='win32')return Promise.reject(Error('Requires an unlocked Windows desktop'));
 if(!actions.includes(args.action))return Promise.reject(Error('Unknown action'));
 return new Promise((resolve,reject)=>{
  const child=spawn('powershell.exe',['-NoLogo','-NoProfile','-NonInteractive','-STA','-File',path.join(__dirname,'desktop.ps1')],{windowsHide:true,stdio:['pipe','pipe','pipe']});
  let output='',error='',settled=false;
  const timer=setTimeout(()=>{child.kill();done(Error('Desktop action timed out; observe before retrying. '+error.trim()));},20000);
  function done(err,value){if(settled)return;settled=true;clearTimeout(timer);err?reject(err):resolve(value);}
  child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');
  child.stdout.on('data',s=>{output+=s;if(output.length>16*1024*1024){child.kill();done(Error('Desktop response too large'));}});
  child.stderr.on('data',s=>{error=(error+s).slice(-4000);});
  child.on('error',e=>done(e));child.on('close',code=>{try{if(code)throw Error(error||'Desktop action failed');const r=JSON.parse(output);if(r.error)throw Error(r.error);done(null,r);}catch(e){done(e);}});
  child.stdin.on('error',()=>{});child.stdin.end(Buffer.from(JSON.stringify(args)).toString('base64')+'\n');
 });
}
const tool={name:'desktop',description:'Observe and operate the existing Windows desktop, apps and signed-in browser windows. Foreground control; observe first. It does not use the separate Playwright browser profile. Coordinates are original desktop pixels, including negative monitor origins. Read screenshot dimensions/scale before clicking. After an action observe its result. No automatic retries.',inputSchema:{type:'object',properties:{action:{type:'string',enum:actions},window:{type:'integer',description:'Window handle from observe'},x:{type:'integer'},y:{type:'integer'},button:{type:'string',enum:['left','right','double']},text:{type:'string'},key:{type:'string',enum:['ENTER','TAB','ESC','BACKSPACE','DELETE','CTRL+A','CTRL+C','CTRL+V','CTRL+L','CTRL+S','ALT+F4','LEFT','RIGHT','UP','DOWN','HOME','END','PAGEUP','PAGEDOWN']},amount:{type:'integer',minimum:-20,maximum:20}},required:['action'],additionalProperties:false}};
async function start(){
 const server=new Server({name:'tokenbots-windows-desktop',version:'1.0.0'},{capabilities:{tools:{}}});
 server.setRequestHandler(ListToolsRequestSchema,async()=>({tools:[tool]}));
 server.setRequestHandler(CallToolRequestSchema,async request=>{
  try {if(request.params.name!=='desktop')throw Error('Unknown tool');const result=await invoke(request.params.arguments||{}),png=result.png;delete result.png;
   return {content:[{type:'text',text:JSON.stringify(result)},...(png?[{type:'image',data:png,mimeType:'image/png'}]:[])]};
  }catch(e){return {isError:true,content:[{type:'text',text:e.message}]};}
 });
 await server.connect(new StdioServerTransport());
}
module.exports={invoke,tool};if(require.main===module)start().catch(()=>{process.exitCode=1;});
