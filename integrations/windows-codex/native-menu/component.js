// Inserted into the reviewed profile module. ma = its React, $ = JSX, O = native MenuItem.
function TokenBotsNativeUsage() {
  const [status, setStatus] = ma.useState(null);
  const [error, setError] = ma.useState('');
  const [expanded, setExpanded] = ma.useState(false);
  const [busy, setBusy] = ma.useState(false);
  const reload = async () => {
    try {
      const response = await fetch('app://-/tokenbots-native/usage', {cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '用量暂不可用');
      setStatus(data); setError('');
    } catch { setStatus(null); setError('用量暂不可用'); }
  };
  ma.useEffect(() => {
    let live = true;
    const refresh = async () => {
      try {
        const response = await fetch('app://-/tokenbots-native/usage', {cache: 'no-store'});
        const data = await response.json();
        if (!response.ok) throw new Error();
        if (live) { setStatus(data); setError(''); }
      } catch { if (live) { setStatus(null); setError('用量暂不可用'); } }
    };
    refresh();
    const timer = setInterval(refresh, 30000);
    return () => { live = false; clearInterval(timer); };
  }, []);
  const accountPercent = account => {
    if (status?.snapshot_stale || account.snapshot_stale) return '待更新';
    const windows = account.windows || [];
    const fresh = windows.filter(w => !w.stale && typeof w.remaining_percent === 'number' && Number.isFinite(w.remaining_percent) && Date.parse(w.resets_at) > Date.now());
    if (!fresh.length) return '未知';
    const minimum = Math.min(...fresh.map(w => Math.max(0, Math.min(100, w.remaining_percent))));
    return `${minimum}%${fresh.length < windows.length ? '（部分窗口）' : ''}`;
  };
  const accounts = (status?.accounts || []).filter(a => status.selected_pool === 'auto' || a.label.toLowerCase() === status.selected_pool);
  const summary = error || (!status ? '读取中…' : accounts.map(a => `${a.label} ${accountPercent(a)}`).join(' · ') || '未知');
  const select = async pool => {
    if (busy) return;
    setBusy(true);
    try {
      const response = await fetch('app://-/tokenbots-native/pool', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({pool})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '切换失败');
      await reload();
    } catch (e) { setError(e.message || '切换失败'); }
    finally { setBusy(false); }
  };
  return $.jsxs($.Fragment, {children: [
    $.jsx(O, {
      onClick: e => { e?.preventDefault?.(); setExpanded(!expanded); },
      rightIcon: $.jsx('span', {'data-tokenbots-remaining': true, style: {fontSize: 12, maxWidth: 190, whiteSpace: 'normal', textAlign: 'right'}, children: summary}),
      children: '使用情况',
    }),
    expanded ? $.jsxs('div', {
      'data-tokenbots-native-usage': true,
      style: {padding: '8px 12px', maxWidth: 370, fontSize: 12, lineHeight: 1.6},
      onClick: e => e.stopPropagation(),
      children: [
        $.jsx('div', {children: 'TokenBots 订阅号池 · 每 30 秒刷新'}),
        ...(status?.accounts || []).map(account => $.jsxs('div', {style: {marginTop: 8}, children: [
          $.jsx('strong', {children: account.label}),
          ...(account.windows || []).map(w => $.jsx('div', {children: `${w.label}：${!status.snapshot_stale && !account.snapshot_stale && !w.stale && typeof w.remaining_percent === 'number' && Date.parse(w.resets_at) > Date.now() ? w.remaining_percent + '%' : '未知 / 待更新'}${w.resets_at ? ' · 重置 ' + new Date(w.resets_at).toLocaleString() : ''}`}, w.label)),
        ]}, account.label)),
        $.jsx('div', {style: {marginTop: 8}, children: '号池：' + (status?.selected_pool || '未知')}),
        $.jsx('div', {style: {display: 'flex', gap: 6}, children: ['auto', 'plus', 'pro'].map(pool => $.jsx('button', {
          type: 'button', disabled: busy || !!status?.active_requests,
          style: {padding: '3px 8px', border: '1px solid currentColor', borderRadius: 6, opacity: status?.selected_pool === pool ? 1 : 0.65},
          onClick: e => { e.preventDefault(); e.stopPropagation(); select(pool); },
          children: pool === 'auto' ? '自动' : pool === 'plus' ? 'Plus' : 'Pro',
        }, pool))}),
        $.jsx('div', {style: {marginTop: 8}, children: '平台不设消费限额；仍受订阅窗口限制。切换后请新建对话。'}),
      ],
    }) : null,
  ]});
}
