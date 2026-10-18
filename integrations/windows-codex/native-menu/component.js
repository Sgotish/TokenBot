// Inserted into the reviewed profile module. ma = its React, $ = JSX, O = native MenuItem.
function TokenBotsNativeUsage() {
  const [status, setStatus] = ma.useState(null);
  const [error, setError] = ma.useState('');
  const [expanded, setExpanded] = ma.useState(false);
  const [busy, setBusy] = ma.useState(false);
  const [checkedAt, setCheckedAt] = ma.useState(null);
  const reload = async () => {
    try {
      const response = await fetch('app://-/tokenbots-native/usage', {cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '用量暂不可用');
      setStatus(data); setError(''); setCheckedAt(new Date().toLocaleTimeString());
    } catch { setStatus(null); setError('用量暂不可用'); }
  };
  ma.useEffect(() => {
    let live = true;
    const refresh = async () => {
      try {
        const response = await fetch('app://-/tokenbots-native/usage', {cache: 'no-store'});
        const data = await response.json();
        if (!response.ok) throw new Error();
        if (live) { setStatus(data); setError(''); setCheckedAt(new Date().toLocaleTimeString()); }
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
  const accounts = (status?.accounts || []).filter(a => status.selected_pool === 'auto' || a.label.toLowerCase().split(/[ ·]/)[0] === status.selected_pool);
  const summary = error || (!status ? '读取中…' : accounts.map(a => `${a.label.split(' ·')[0]} ${accountPercent(a)}`).join(' · ') || '未知');
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
      style: {padding: '8px 12px', maxWidth: 370, maxHeight: '55vh', overflowY: 'auto', fontSize: 12, lineHeight: 1.6},
      onClick: e => e.stopPropagation(),
      children: [
        $.jsx('div', {children: '每 30 秒检查 · 上游额度约每分钟更新'}),
        $.jsx('div', {children: '本次检查：' + (checkedAt || '读取中')}),
        $.jsx('button', {type: 'button', onClick: e => {e.preventDefault(); e.stopPropagation(); reload();}, children: '刷新显示'}),
        $.jsx('div', {style: {marginTop: 8}, children: '号池：' + (status?.selected_pool || '未知')}),
        $.jsx('div', {style: {display: 'flex', gap: 6}, children: ['auto', 'plus', 'pro'].map(pool => $.jsx('button', {
          type: 'button', disabled: busy || !!status?.active_requests,
          style: {padding: '3px 8px', border: '1px solid currentColor', borderRadius: 6, opacity: status?.selected_pool === pool ? 1 : 0.65},
          onClick: e => { e.preventDefault(); e.stopPropagation(); select(pool); },
          children: pool === 'auto' ? '自动' : pool === 'plus' ? 'Plus' : 'Pro',
        }, pool))}),
        ...(status?.accounts || []).map(account => $.jsxs('div', {style: {marginTop: 8}, children: [
          $.jsx('strong', {children: account.label}),
          $.jsx('div', {children: '上游更新时间：' + (account.snapshot_at ? new Date(account.snapshot_at).toLocaleString() : '未知')}),
          account.refresh_error ? $.jsx('div', {role: 'status', children: account.refresh_error}) : null,
          ...(account.windows || []).map(w => $.jsx('div', {children: `${w.label}：${!status.snapshot_stale && !account.snapshot_stale && !w.stale && typeof w.remaining_percent === 'number' && Number.isFinite(w.remaining_percent) && Date.parse(w.resets_at) > Date.now() ? w.remaining_percent + '%' : (w.reason || '历史数据 / 待更新')}${w.remaining_percent !== null && w.resets_at ? ' · 重置 ' + new Date(w.resets_at).toLocaleString() : ''}`}, w.label)),
        ]}, account.label)),
        $.jsx('div', {style: {marginTop: 8}, children: '平台不设消费限额；仍受订阅窗口限制。切换后请新建对话。'}),
      ],
    }) : null,
  ]});
}
