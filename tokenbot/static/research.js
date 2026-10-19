'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let key = '', data = null;
  const number = x => Number.isFinite(x) ? x.toLocaleString('zh-CN', {maximumFractionDigits: 2}) : '—';
  const million = x => !Number.isFinite(x) ? '—' : x >= 1e6 ? number(x / 1e6) + ' M' : x >= 1000 ? number(x / 1000) + ' K' : number(x);
  const money = x => x.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 6});
  const date = x => x ? new Date(x * 1000).toLocaleString('zh-CN') : '尚无';
  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function table(headers, rows) {
    const scroll = el('div', undefined, 'scroll'), t = el('table'), head = el('thead'), tr = el('tr');
    headers.forEach(v => tr.append(el('th', v))); head.append(tr); t.append(head);
    const body = el('tbody');
    rows.forEach(row => { const line = el('tr'); row.forEach(v => {
      const td = el('td'); if (v instanceof Node) td.append(v); else td.textContent = v; line.append(td);
    }); body.append(line); });
    t.append(body); scroll.append(t); return scroll;
  }
  function scenario() {
    const values = ['cost', 'overhead', 'util', 'fee', 'margin'].map(id => $(id).value.trim() === '' ? NaN : Number($(id).value));
    const [cost, overhead, util, fee, margin] = values;
    if (!values.every(Number.isFinite) || cost < 0 || overhead < 0 || util <= 0 || util > 100 || fee < 0 || margin < 0 || fee + margin >= 100) {
      $('scenario-error').textContent = '请填写有效成本与比例；费率和利润率之和必须小于 100%。'; return null;
    }
    $('scenario-error').textContent = '';
    return {cost: cost + overhead, utilization: util / 100, fee: fee / 100, margin: margin / 100};
  }
  function prices(capacity, assumptions, available) {
    if (!assumptions || !available || !capacity) return '—';
    const unit = assumptions.cost / (capacity / 1e6 * assumptions.utilization);
    return '$' + money(unit / (1 - assumptions.fee)) + ' / $' + money(unit / (1 - assumptions.fee - assumptions.margin));
  }
  function render() {
    if (!data) return;
    const a = data.accounts.find(a => a.account === $('account').value);
    if (!a) return;
    const assumptions = scenario();
    const stale = data.report_stale || data.ledger_stale || data.collection_failed;
    $('freshness').textContent = '报告更新：' + date(data.generated_at) + ' · 完整日志扫描：' + date(data.last_complete_scan) + ' · 历史范围起点：' + date(data.history_start);
    $('message').textContent = stale ? '采集尚未完成或数据已过期，保留历史记录，暂不展示参考售价。' : '';
    $('actual').replaceChildren();
    a.actual.forEach(period => {
      const title = {'5h':'最近 5 小时', '7d':'最近 7 天', '30d':'最近 30 天'}[period.period];
      $('actual').append(el('h3', title + (period.complete ? ' · 已覆盖（末尾 2 分钟待结算）' : ' · 部分记录')));
      const rows = Object.entries(period.models).map(([model, m]) => [model, number(m.requests), million(m.tokens), million(m.input_tokens), million(m.output_tokens), million(m.cache_read_tokens), million(m.cache_creation_tokens), number(m.invalid_records)]);
      if (!rows.length) $('actual').append(el('p', '尚无已采集的调用记录。', 'muted'));
      else $('actual').append(table(['模型','请求','已统计 Token','普通输入','输出','缓存读','缓存写','不能校准的记录'], rows));
    });
    $('estimates').replaceChildren();
    const reasons = {reset:'跨重置周期',snapshot_gap:'额度快照缺口',quota_decreased:'额度回退',ledger_gap:'日志范围不完整',invalid_usage:'缺失字段或非文本用量',quota_without_tokens:'有额度消耗但无 Token',boundary_uncertainty:'边界请求误差过大'};
    a.windows.forEach(w => {
      const latest = w.last_snapshot;
      const fresh = latest && data.generated_at - latest.stamp <= 900;
      $('estimates').append(el('h3', (w.seconds === 604800 ? '周窗口' : '5 小时窗口') + ' · ' + w.snapshots + ' 个快照'));
      if (latest) $('estimates').append(el('p', '最近已用 ' + number(latest.used) + '% · 观测于 ' + date(latest.stamp) + ' · 重置 ' + date(latest.reset), 'muted'));
      if (!w.estimates.length) $('estimates').append(el('p', latest ? '正在积累有效样本，尚不能换算容量与价格。额度不变不代表调用免费。' : '上游未提供可用窗口快照，暂不推算此窗口的容量。', 'note'));
      else {
        const rows = w.estimates.map(e => {
          const name = el('div', e.cohort ? e.cohort[0] : '全部有效样本 · 当前混合负载');
          name.append(el('small', e.cohort ? '推理：' + e.cohort[1] + ' / 速度：' + e.cohort[2] : '不按 Token 比例拆分各模型额度'));
          name.append(el('small', (e.status === 'provisional' ? '初步样本' : '已积累样本') + ' · ' + e.blocks + ' 段 / ' + number(e.points) + ' 个百分点'));
          name.append(el('small', '输入 / 输出 / 缓存读 / 缓存写：' + ['input_tokens','output_tokens','cache_read_tokens','cache_creation_tokens'].map(k => number(e.composition[k] / e.tokens * 100) + '%').join(' / ')));
          const rate = el('div', number(e.points_per_million) + ' pp / M');
          rate.append(el('small', '敏感区间 ' + e.rate_sensitivity.map(number).join(' – ')));
          return [name, rate, million(e.window_capacity_tokens), million(e.monthly_capacity_tokens), prices(e.monthly_capacity_tokens, assumptions, !stale && fresh)];
        });
        $('estimates').append(table(['负载与样本','每百万消耗','完整窗口容量','30 天情景容量','保本 / 目标价（每百万）'], rows));
      }
      const exclusions = Object.entries(w.excluded).map(([k,v]) => (reasons[k] || k) + ' ' + v + ' 段');
      if (exclusions.length) $('estimates').append(el('p', '未纳入估算：' + exclusions.join('；'), 'muted'));
    });
    $('limitations').replaceChildren(...data.limitations.map(v => el('li', v)));
  }
  async function load() {
    $('refresh').disabled = true;
    try {
      const response = await fetch('/research/api/report', {headers: {Authorization: 'Bearer ' + key}, cache: 'no-store', credentials: 'omit', redirect: 'error'});
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || '读取失败');
      data = body;
      const previous = $('account').value;
      $('account').replaceChildren(...data.accounts.map(a => {const option = el('option', a.label); option.value = a.account; return option;}));
      if (data.accounts.some(a => a.account === previous)) $('account').value = previous;
      $('login').hidden = true; $('dashboard').hidden = false; render();
    } catch (error) {
      data = null; $('dashboard').hidden = true; $('login').hidden = false;
      $('message').textContent = error.message || '连接暂时失败，请重试。';
    } finally { $('refresh').disabled = false; }
  }
  $('login-form').addEventListener('submit', event => {event.preventDefault(); key = $('key').value.trim(); $('key').value = ''; load();});
  $('refresh').addEventListener('click', load);
  $('logout').addEventListener('click', () => {key = ''; data = null; $('dashboard').hidden = true; $('login').hidden = false; $('message').textContent = ''; $('actual').replaceChildren(); $('estimates').replaceChildren();});
  $('account').addEventListener('change', render);
  ['cost','overhead','util','fee','margin'].forEach(id => $(id).addEventListener('input', render));
})();
