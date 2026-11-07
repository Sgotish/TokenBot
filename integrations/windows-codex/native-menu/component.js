// Inserted into the reviewed profile module. ma = React, $ = JSX, O = MenuItem.
function TokenBotsNativeUsage() {
  const [status, setStatus] = ma.useState(null);
  const [error, setError] = ma.useState('');
  const [expanded, setExpanded] = ma.useState(false);
  const [busy, setBusy] = ma.useState(false);
  const reload = async () => {
    try {
      const response = await fetch('app://-/tokenbots-native/usage', {cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error();
      setStatus(data); setError('');
    } catch { setStatus(null); setError('暂不可用'); }
  };
  ma.useEffect(() => {
    let live = true;
    const refresh = async () => {
      try {
        const response = await fetch('app://-/tokenbots-native/usage', {cache: 'no-store'});
        const data = await response.json();
        if (!response.ok) throw new Error();
        if (live) { setStatus(data); setError(''); }
      } catch { if (live) { setStatus(null); setError('暂不可用'); } }
    };
    refresh();
    const timer = setInterval(refresh, 30000);
    return () => { live = false; clearInterval(timer); };
  }, []);
  const freshWindows = account => status?.snapshot_stale || account.snapshot_stale ? [] :
    (account.windows || []).filter(w => !w.stale && typeof w.remaining_percent === 'number' && Number.isFinite(w.remaining_percent) && Date.parse(w.resets_at) > Date.now());
  const percent = n => Math.max(0, Math.min(100, n));
  const accountPercent = account => {
    const windows = freshWindows(account);
    return windows.length ? Math.min(...windows.map(w => percent(w.remaining_percent))) + '%' : '待更新';
  };
  const plan = a => a.label.split(' ·')[0];
  const accounts = (status?.accounts || []).filter(a => status.selected_pool === 'auto' || plan(a).toLowerCase() === status.selected_pool);
  const allowance = status?.allowance;
  const amount = allowance?.remaining;
  const ownBalance = allowance && ((status.snapshot_stale || status.error || amount == null)
    ? '余额待更新' : (allowance.trial ? '试用剩余 ¥' : '站内剩余 $') +
      Number(amount).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 8}));
  const summary = error || ownBalance || (!status ? '读取中…' : accounts.map(a => `${plan(a)} ${accountPercent(a)}`).join(' · ') || '待更新');
  const select = async pool => {
    if (busy) return;
    setBusy(true);
    try {
      const response = await fetch('app://-/tokenbots-native/pool', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({pool})});
      if (!response.ok) throw new Error();
      await reload();
    } catch { setError('切换失败'); }
    finally { setBusy(false); }
  };
  return $.jsxs($.Fragment, {children: [
    $.jsx(O, {
      onClick: e => { e?.preventDefault?.(); setExpanded(!expanded); },
      rightIcon: $.jsx('span', {'data-tokenbots-remaining': true, style: {fontSize: 12, maxWidth: 190, textAlign: 'right'}, children: summary}),
      children: '使用情况',
    }),
    expanded ? $.jsxs('div', {
      'data-tokenbots-native-usage': true,
      style: {padding: '8px 12px', minWidth: 220, fontSize: 12, lineHeight: 1.6},
      onClick: e => e.stopPropagation(),
      children: [
        $.jsx('div', {style: {display: 'flex', gap: 6, marginBottom: 8}, children: ['auto', 'plus', 'pro'].map(pool => $.jsx('button', {
          type: 'button', disabled: busy || !!status?.active_requests, 'aria-pressed': status?.selected_pool === pool,
          style: {padding: '3px 8px', border: '1px solid currentColor', borderRadius: 6, opacity: status?.selected_pool === pool ? 1 : 0.65},
          onClick: e => { e.preventDefault(); e.stopPropagation(); select(pool); },
          children: pool === 'auto' ? '自动' : pool === 'plus' ? 'Plus' : 'Pro',
        }, pool))}),
        ...accounts.map(account => $.jsxs('div', {style: {marginTop: 8}, children: [
          $.jsx('strong', {children: plan(account) + ' 套餐余量'}),
          ...freshWindows(account).map(w => $.jsxs('div', {style: {marginTop: 4}, children: [
            $.jsxs('div', {style: {display: 'flex', justifyContent: 'space-between', gap: 12}, children: [
              $.jsx('span', {children: w.label.replace('窗口', '')}),
              $.jsx('span', {children: percent(w.remaining_percent) + '%'}),
            ]}),
            $.jsx('progress', {value: percent(w.remaining_percent), max: 100, 'aria-label': plan(account) + ' ' + w.label, style: {width: '100%', height: 5, accentColor: 'currentColor'}}),
          ]}, w.label)),
          !freshWindows(account).length ? $.jsx('div', {role: 'status', children: '余量待更新'}) : null,
        ]}, account.label)),
      ],
    }) : null,
    $.jsx(TokenBotsNativeUpdate, {}),
  ]});
}

function TokenBotsNativeUpdate() {
  const [open,setOpen]=ma.useState(false);
  const [info,setInfo]=ma.useState(null);
  const [busy,setBusy]=ma.useState(false);
  const [error,setError]=ma.useState('');
  ma.useEffect(()=>{
    let live=true;
    const refresh=async()=>{try{
      const r=await fetch('app://-/tokenbots-native/update',{cache:'no-store'});
      if(!r.ok)throw Error(); const value=await r.json();
      if(live)setInfo(value);
    }catch{if(live)setError('无法读取更新状态，请重试。');}};
    refresh(); const timer=setInterval(refresh,3000);
    return()=>{live=false;clearInterval(timer);};
  },[]);
  const act=async action=>{
    if(busy)return; setBusy(true);setError('');setOpen(true);
    setInfo(old=>({...old,state:action==='check'?'checking':'downloading'}));
    try{
      const r=await fetch('app://-/tokenbots-native/update/'+action,{method:'POST'});
      const value=await r.json();setInfo(value);
      if(!r.ok)throw Error(value.error||'操作未完成，请重试。');
    }catch(e){setError(e.message||'网络异常，请重试。');}
    finally{setBusy(false);}
  };
  const working=busy||['checking','downloading'].includes(info?.state);
  const labels={latest:'已经检查过，是最新版本',available:'发现新版本',ready:'更新已下载，等待重启安装',installed:'更新已安装，请检查最新版本',checking:'正在检查更新…',downloading:'正在下载并校验更新…',error:'更新未完成，请重试'};
  const when=value=>value?new Date(value).toLocaleString():'尚无记录';
  return $.jsxs($.Fragment,{children:[
    $.jsx(O,{onClick:e=>{e?.preventDefault?.();act('check');},children:'检查更新'}),
    open?$.jsxs('div',{'data-tokenbots-update':true,role:'status',style:{padding:'8px 12px',width:'100%',boxSizing:'border-box',whiteSpace:'normal',overflowWrap:'anywhere',fontSize:12,lineHeight:1.8},onClick:e=>e.stopPropagation(),children:[
      $.jsx('strong',{children:error||labels[info?.state]||'尚未检查更新'}),
      $.jsx('div',{children:'当前定制版本：'+(info?.installedVersion||'旧版，等待更新')}),
      info?.latestVersion?$.jsx('div',{children:'发布版本：'+info.latestVersion}):null,
      $.jsx('div',{children:'上次检查：'+when(info?.lastCheckedAt)}),
      $.jsx('div',{children:'Last update（上次更新）：'+when(info?.lastUpdatedAt)}),
      info?.error?$.jsx('div',{children:info.error}):null,
      ['available','error'].includes(info?.state)?$.jsx('button',{disabled:working,onClick:e=>{e.preventDefault();act('download');},children:'更新'}):null,
      info?.state==='ready'?$.jsx('div',{children:'请先保存任务，完全退出 TokenBots Codex，再用桌面快捷方式打开，完成安装。'}):null,
      $.jsx('button',{disabled:working,onClick:e=>{e.preventDefault();setOpen(false);},children:'收起'}),
    ]}):null,
  ]});
}
