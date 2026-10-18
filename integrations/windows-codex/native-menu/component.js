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
  const summary = error || (!status ? '读取中…' : accounts.map(a => `${plan(a)} ${accountPercent(a)}`).join(' · ') || '待更新');
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
  ]});
}
