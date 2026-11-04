'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {randomUUID} = require('node:crypto');
const readline = require('node:readline');
const tool = {
  name:'generate_image', description:'Generate one real PNG with TokenBots and save it to the user’s Pictures/TokenBots folder. Return the local path for display in chat.',
  inputSchema:{type:'object', properties:{prompt:{type:'string', description:'Visual description of the image requested by the user'}}, required:['prompt'], additionalProperties:false}
};
async function generate(prompt) {
  if (typeof prompt !== 'string' || !prompt.trim() || prompt.length > 16000) throw Error('请输入一段不超过 16000 字的图片描述。');
  const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8').replace(/^\uFEFF/, ''));
  if ((config.origin || config.public_origin) !== 'https://pilot.tokenbots.top' || !config.key) throw Error('请检查本机 TokenBots 接入配置。');
  const response = await fetch('https://pilot.tokenbots.top/v1/responses', {
    method:'POST', redirect:'error', signal:AbortSignal.timeout(210000),
    headers:{'Content-Type':'application/json',Authorization:'Bearer '+config.key},
    body:JSON.stringify({model:'gpt-6.1-sol', reasoning:{effort:'low'},store:false,stream:true,
      instructions:'Generate one image using the requested tool.', input:[{role:'user',content:prompt}],
      tools:[{type:'image_generation',quality:'low'}],tool_choice:{type:'image_generation'}})
  });
  if (!response.ok) throw Error('生图请求失败 HTTP '+response.status+'。请检查余额和用量记录。');
  let image, completed=false;
  for await (const line of readline.createInterface({input:require('node:stream').Readable.fromWeb(response.body),crlfDelay:Infinity})) {
    if (!line.startsWith('data:')) continue;
    const payload=line.slice(5).trim();
    if (!payload || payload==='[DONE]') continue;
    const event=JSON.parse(payload);
    if (event.type==='response.output_item.done' && event.item?.type==='image_generation_call') image=event.item.result;
    if (event.type==='response.failed' || event.type==='error') throw Error('上游生成失败，请查看用量记录后再试。');
    if (event.type==='response.completed') {image ||= event.response?.output?.find(i=>i.type==='image_generation_call')?.result; completed=true;break;}
  }
  if (!completed || typeof image!=='string') throw Error('没有收到完整的图片。');
  const bytes=Buffer.from(image,'base64');
  if (!bytes.subarray(0,8).equals(Buffer.from('89504e470d0a1a0a','hex'))) throw Error('图片格式校验失败。');
  const directory=path.join(os.homedir(),'Pictures','TokenBots');
  fs.mkdirSync(directory,{recursive:true,mode:0o700});
  const file=path.join(directory,randomUUID()+'.png');
  fs.writeFileSync(file,bytes,{flag:'wx',mode:0o600});
  return {content:[{type:'text',text:'PNG 已保存。请用 Markdown 图片语法向用户展示这个本地文件：'+file}]};
}
async function dispatch(msg) {
  if (!Object.hasOwn(msg,'id')) return;
  let result;
  if (msg.method==='initialize') result={protocolVersion:['2024-11-05','2025-03-26','2025-06-18','2025-11-25'].includes(msg.params?.protocolVersion)?msg.params.protocolVersion:'2025-06-18',capabilities:{tools:{}},serverInfo:{name:'tokenbots-images',version:'1.0.0'}};
  else if (msg.method==='tools/list') result={tools:[tool]};
  else if (msg.method==='ping') result={};
  else if (msg.method==='tools/call' && msg.params?.name===tool.name) {
    try { result=await generate(msg.params.arguments?.prompt); }
    catch(e) {result={isError:true,content:[{type:'text',text:e.message.startsWith('生图')||e.message.startsWith('请')||e.message.startsWith('没有')||e.message.startsWith('上游')?e.message:'生图未完成，请检查网络和本机图片目录。'}]};}
  } else return {jsonrpc:'2.0',id:msg.id,error:{code:-32601,message:'Method not found'}};
  return {jsonrpc:'2.0',id:msg.id,result};
}
readline.createInterface({input:process.stdin}).on('line',async line=>{
  try {const reply=await dispatch(JSON.parse(line));if(reply)process.stdout.write(JSON.stringify(reply)+'\n');}catch{}
});
