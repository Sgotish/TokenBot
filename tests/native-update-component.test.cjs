const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const code=fs.readFileSync('integrations/windows-codex/native-menu/component.js','utf8');
test('native menu exposes check, truthful status, timestamps, download and safe restart instructions',async()=>{
 const values=[false,null,false,''];let cursor=0,server={state:'latest',installedVersion:22,latestVersion:22,lastCheckedAt:'2026-11-06T10:00:00Z',lastUpdatedAt:'2026-11-05T10:00:00Z'};
 const requests=[];
 const ctx={ma:{useState(initial){const i=cursor++;return [values[i]??initial,v=>values[i]=typeof v==='function'?v(values[i]):v];},useEffect(){}},$:{jsx:(type,props)=>({type,props}),jsxs:(type,props)=>({type,props}),Fragment:'fragment'},O:'menu',fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>server};}};
 vm.createContext(ctx);vm.runInContext(code,ctx);
 function render(){cursor=0;return ctx.TokenBotsNativeUpdate();}
 function flat(node){if(!node)return [];return [node,...(Array.isArray(node.props?.children)?node.props.children:[]).flatMap(flat)];}
 const click={preventDefault(){}};
 await render().props.children[0].props.onClick(click);
 // onClick starts its async action; drain awaited fetch/json.
 await new Promise(r=>setImmediate(r));
 let text=JSON.stringify(render());assert.match(text,/已经检查过，是最新版本/);assert.match(text,/Last update/);assert.match(text,/上次检查/);
 server={...server,state:'available',latestVersion:23};
 render().props.children[0].props.onClick(click);await new Promise(r=>setImmediate(r));
 let tree=render();assert.match(JSON.stringify(tree),/发现新版本/);
 const update=flat(tree).find(n=>n.type==='button'&&n.props.children==='更新');assert(update);
 server={...server,state:'ready'};update.props.onClick(click);await new Promise(r=>setImmediate(r));
 assert.match(requests.at(-1).url,/\/download$/);assert.match(JSON.stringify(render()),/先保存任务/);
 assert(!requests.some(r=>/apply|restart/.test(r.url)),'no mid-task forced replacement');
});
