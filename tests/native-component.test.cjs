const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const code = fs.readFileSync('integrations/windows-codex/native-menu/component.js', 'utf8');
const future = new Date(Date.now() + 3600000).toISOString();
function render(status) {
  let index = 0;
  const context = {Date, Math, Number, JSON, setInterval, clearInterval,
    ma: {useState: () => [[status, '', true, false][index++], () => {}], useEffect: () => {}},
    $: {Fragment: 'fragment', jsx: (type, props) => ({type, ...props}), jsxs: (type, props) => ({type, ...props})}, O: 'MenuItem'};
  vm.createContext(context);
  vm.runInContext(code, context);
  return context.TokenBotsNativeUsage();
}
function account(label, percent, stale = false) {
  return {label, snapshot_stale: stale, windows: [{label: '5h', remaining_percent: percent, stale, resets_at: future}]};
}
test('native summary follows selected pool with actual backend account labels', () => {
  const result = render({selected_pool: 'plus', accounts: [account('Pro · 账号 1', 91), account('Plus · 账号 2', 94)]});
  assert.equal(result.children[0].children, '使用情况');
  assert.equal(result.children[0].rightIcon.children, 'Plus 94%');
});
test('stale or expired windows cannot appear as current remaining percentage', () => {
  let a = account('Plus · 账号 2', 94, true);
  assert.match(render({selected_pool: 'plus', accounts: [a]}).children[0].rightIcon.children, /待更新/);
  a = account('Plus · 账号 2', 94);
  a.windows[0].resets_at = '2000-01-01T00:00:00Z';
  assert.match(render({selected_pool: 'plus', accounts: [a]}).children[0].rightIcon.children, /未知/);
});
test('auto mode reports separate accounts and flags partially known windows', () => {
  const a = account('Pro', 91);
  a.windows.push({label: '7d', remaining_percent: null, stale: true});
  const text = render({selected_pool: 'auto', accounts: [a, account('Plus', 94)]}).children[0].rightIcon.children;
  assert.equal(text, 'Pro 91%（部分窗口） · Plus 94%');
});
