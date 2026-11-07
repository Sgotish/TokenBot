const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn}=require('node:child_process');
process.env.TOKENBOTS_DESKTOP_DEBUG='1';
const {Client}=require('../integrations/windows-codex/browser-tools/node_modules/@modelcontextprotocol/sdk/dist/cjs/client/index.js');
const {StdioClientTransport}=require('../integrations/windows-codex/browser-tools/node_modules/@modelcontextprotocol/sdk/dist/cjs/client/stdio.js');
const assert=require('node:assert/strict');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'tb-desktop-')),result=path.join(dir,'result.json'),fixture=path.join(dir,'window.ps1');
 const output=path.resolve('reports/windows-desktop-20261107');fs.mkdirSync(output,{recursive:true});
 fs.writeFileSync(fixture,`Add-Type -AssemblyName System.Windows.Forms\n$f=New-Object Windows.Forms.Form\n$f.Text='TokenBots Desktop Acceptance'\n$f.Width=650;$f.Height=400;$f.StartPosition='CenterScreen'\n$t=New-Object Windows.Forms.TextBox\n$t.Left=30;$t.Top=40;$t.Width=500\n$b=New-Object Windows.Forms.Button\n$b.Text='Verify';$b.Left=30;$b.Top=100;$b.Width=130\n$b.Add_Click({@{text=$t.Text;clicked=$true}|ConvertTo-Json|Set-Content -Encoding UTF8 -LiteralPath '${result.replace(/'/g,"''")}'})\n$u=New-Object Windows.Forms.Button\n$u.Text='Upload';$u.Left=180;$u.Top=100;$u.Width=130\n$u.Add_Click({$d=New-Object Windows.Forms.OpenFileDialog;$d.Multiselect=$true;if($d.ShowDialog() -eq 'OK'){@{files=@($d.FileNames)}|ConvertTo-Json|Set-Content -Encoding UTF8 -LiteralPath '${path.join(dir,'upload.json').replace(/'/g,"''")}'}})\n$f.Controls.Add($t);$f.Controls.Add($b);$f.Controls.Add($u);$f.TopMost=$true\n[void]$f.ShowDialog()\n`);
 const ui=spawn('powershell.exe',['-NoLogo','-NoProfile','-STA','-File',fixture],{windowsHide:false,stdio:['ignore','pipe','pipe']});
 ui.stderr.on('data',s=>process.stderr.write(s));
 ui.on('exit',c=>console.log('Fixture process exited',c));
 const deadline=setTimeout(()=>{console.error('Desktop test deadline');ui.kill();process.exit(1);},120000);
 const client=new Client({name:'desktop-acceptance',version:'1.0.0'});
 const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve('integrations/windows-codex/browser-tools/desktop.cjs')],env:{...process.env,TOKENBOTS_DESKTOP_DEBUG:'1'},stderr:'pipe'});
 async function call(a){const r=await client.callTool({name:'desktop',arguments:a});assert.ok(!r.isError,JSON.stringify(r));return r;}
 try{
 await client.connect(transport);assert.ok((await client.listTools()).tools.some(t=>t.name==='desktop'));
 let state,window;
 for(let i=0;i<15;i++){const r=await call({action:'observe'});state=JSON.parse(r.content[0].text);window=state.windows.find(w=>w.title==='TokenBots Desktop Acceptance');if(window)break;await new Promise(r=>setTimeout(r,500));}
 fs.writeFileSync(path.join(output,'observed-windows.json'),JSON.stringify(state));
 assert.ok(window,'Fixture window missing');
 await call({action:'focus',window:window.handle});
 await call({action:'click',x:window.left+80,y:window.top+80});
 await call({action:'type',text:'TokenBots 中文 42'});
 await call({action:'key',key:'TAB'});await call({action:'key',key:'ENTER'});
 for(let i=0;i<10&&!fs.existsSync(result);i++)await new Promise(r=>setTimeout(r,250));
 const value=JSON.parse(fs.readFileSync(result,'utf8').replace(/^\uFEFF/,''));assert.equal(value.text,'TokenBots 中文 42');assert.equal(value.clicked,true);
 const fileNames=['资料 demo.docx','图片 one.png','图片 two.png','图片 three.png','图片 four.png'];
 const files=fileNames.map(n=>path.join(dir,n));for(const f of files)fs.writeFileSync(f,'synthetic picker fixture');
 await call({action:'key',key:'TAB'});await call({action:'key',key:'ENTER'});
 await call({action:'observe'});await call({action:'key',key:'ALT+N'});await call({action:'key',key:'CTRL+A'});
 await call({action:'type',text:files.map(f=>'"'+f+'"').join(' ')});await call({action:'key',key:'ENTER'});
 const upload=path.join(dir,'upload.json');for(let i=0;i<15&&!fs.existsSync(upload);i++)await new Promise(r=>setTimeout(r,250));
 assert.deepEqual(JSON.parse(fs.readFileSync(upload,'utf8').replace(/^\uFEFF/,'')).files.sort(),files.sort());
 const observed=await call({action:'observe'}),img=observed.content.find(c=>c.type==='image');assert.ok(img);fs.writeFileSync(path.join(output,'desktop.png'),Buffer.from(img.data,'base64'));
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({passed:true,windows:state.windows.length,unicodeTyping:true,click:true,keyboard:true,screenshot:true,unicodeMultiFilePicker:true,customerDevice:false}));
 console.log('Actual Windows MCP enumerate/focus/click/Unicode typing/keyboard/screenshot passed');
 }finally{clearTimeout(deadline);ui.kill();await client.close();}
 process.exit(0);
})().catch(e=>{console.error(e);process.exit(1);});
