#!/usr/bin/env python3
"""Read-only cloud readiness check. Credentials stay on the server; no model calls."""
import argparse
import subprocess

REMOTE = r'''
import json, time, urllib.request, subprocess, sys
from pathlib import Path
sys.path.insert(0, '/opt/tokenbot-pilot')
from tokenbot.panel_session import login

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))
def request(url, token=None, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer '+token} if token else {})})
    with opener.open(req, timeout=20) as response:
        return json.load(response)

def main():
    root = Path('/opt/tokenbot-pilot/private')
    collector = json.loads((root/'collector.json').read_text())
    bridge = json.loads((root/'partner.json').read_text())
    base = 'http://127.0.0.1:8180/api/v1'
    def authenticate(credentials):
        return login(lambda method, path, body: request(base+path, body=body)['data'], credentials)
    token = authenticate(collector['admin'])
    def panel(path):
        result = request(base+path, token)
        if result.get('code') != 0:
            raise RuntimeError('Panel returned an error')
        return result['data']
    settings = panel('/admin/settings')
    overview = panel('/admin/ops/dashboard/overview')
    stats = panel('/admin/dashboard/stats')
    logs = panel('/admin/ops/system-logs/health')
    available = panel('/admin/ops/account-availability')
    concurrency = panel('/admin/ops/concurrency')
    models = request(bridge['public_origin']+'/v1/models', bridge['key'])
    usage = request(bridge['public_origin']+'/v1/usage', bridge['key'])
    accounts = [panel('/admin/accounts/'+str(i)) for i in collector['accounts']]
    groups = [panel('/admin/groups/'+str(p['group_id'])) for p in bridge['pools'].values()]
    user_token = authenticate(collector['partner'])
    key_items = request(base+'/keys?page=1&page_size=100', user_token)['data']['items']
    expected_keys = {bridge['key']} | {p['key'] for p in bridge['pools'].values()}
    live_keys = [k for k in key_items if k.get('key') in expected_keys]
    redis = json.loads(subprocess.check_output(['docker', 'inspect', 'tokenbot-pilot-redis-1']))[0]
    env = dict(s.split('=', 1) for s in redis['Config']['Env'] if '=' in s)
    raw = subprocess.check_output(['docker', 'exec', '-e', 'REDISCLI_AUTH='+env['REDIS_PASSWORD'],
        'tokenbot-pilot-redis-1', 'redis-cli', 'INFO', 'memory'], text=True, timeout=10)
    memory = dict(line.split(':', 1) for line in raw.splitlines() if ':' in line)
    used, maximum = int(memory['used_memory']), int(memory['maxmemory'])
    checks = {
        'two_schedulable_accounts': len(accounts) == 2 and all(a.get('status') == 'active' and a.get('schedulable') is True for a in accounts),
        'three_pools': set(bridge['pools']) == {'auto','plus','pro'},
        'zero_test_pool_multiplier': all(g.get('rate_multiplier') == 0 for g in groups),
        'public_model_available': any(m.get('id') == 'gpt-6.1-sol' for m in models.get('data', [])),
        'key_no_expiry': bridge.get('expires_at', 'missing') is None,
        'platform_no_quota': usage.get('platform_quota', 'missing') is None,
        'stored_keys_unlimited': len(live_keys) == len(expected_keys) and all(
            k.get('status') == 'active' and k.get('expires_at', 'missing') is None and
            all(k.get(field) == 0 for field in ('quota','rate_limit_5h','rate_limit_1d','rate_limit_7d'))
            for k in live_keys),
        'monitoring_enabled': settings.get('ops_monitoring_enabled') is True,
        'realtime_monitoring_enabled': settings.get('ops_realtime_monitoring_enabled') is True and available.get('enabled') is True and concurrency.get('enabled') is True,
        'db_and_redis_healthy': overview.get('system_metrics', {}).get('db_ok') is True and overview.get('system_metrics', {}).get('redis_ok') is True,
        'redis_memory_headroom': maximum > 0 and used < maximum*.8,
        'usage_collector_fresh': usage.get('snapshot_stale') is False,
        'upstream_quota_fresh': len(usage.get('accounts', [])) == 2 and all(
            a.get('source') == 'quota_api' and a.get('snapshot_stale') is False and not a.get('refresh_error')
            for a in usage.get('accounts', [])),
        'log_ingestion_healthy': logs.get('dropped_count') == 0 and logs.get('write_failed_count') == 0,
    }
    report = {
        'checked_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'checks': checks,
        'redis_memory': {'used_bytes':used, 'max_bytes':maximum, 'alert_threshold_percent':80},
        'accounts': [{'label': label, 'status': a.get('status'), 'schedulable': a.get('schedulable')} for label,a in zip(collector['accounts'].values(),accounts)],
        'selected_pool': usage.get('selected_pool'),
        'last_hour': {k: overview.get(k) for k in ('request_count_total','success_count','error_count_total','upstream_429_count','token_consumed','duration','ttft')},
        'cumulative_requests': stats.get('total_requests'),
        'limits': ['Read-only readiness, not a model execution or load test.', 'A missing upstream quota window is unknown, not unlimited.'],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1

try:
    raise SystemExit(main())
except Exception:
    print(json.dumps({'error': 'Readiness check failed; credentials and upstream error bodies suppressed.'}))
    raise SystemExit(1)
'''

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ssh_target', help='Existing authorized SSH destination, e.g. root@host')
    args = parser.parse_args()
    if args.ssh_target.startswith('-'):
        parser.error('Invalid SSH target')
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
                             args.ssh_target, 'python3 -'], input=REMOTE, text=True)
    raise SystemExit(result.returncode)
