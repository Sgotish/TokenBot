'use strict';
const path=require('node:path'), crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const home=process.argv[2];
if(!home || !path.isAbsolute(home))throw Error('Expected dedicated Codex home');
const workspace=crypto.createHash('sha256').update(process.cwd()).digest('hex').slice(0,16);
const args=[path.join(path.dirname(require.resolve('@playwright/mcp/package.json')),'cli.js'), '--browser',process.platform==='win32'?'msedge':'chrome',
  '--user-data-dir',path.join(home,'browser-profiles',workspace),
  '--output-dir',path.join(home,'browser-output',workspace),'--output-max-size','16777216'];
// stdio only. Never expose CDP or an MCP server on a network interface.
const child=spawn(process.execPath,args,{stdio:'inherit',windowsHide:true});
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>child.kill(signal));
child.on('error',()=>{console.error('Browser tool could not start');process.exitCode=1;});
child.on('exit',code=>{process.exitCode=code ?? 1;});
