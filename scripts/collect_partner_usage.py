#!/usr/bin/env python3
"""Root-only timer: export a sanitized status file, never expose admin login to web worker."""
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tokenbot.client import NoRedirect
from tokenbot.usage_snapshot import account_view, record_view, quota_view, epoch
from tokenbot.panel_session import login, invalidate


def collect(config, panel_override=None, now_override=None, account_snapshot=None):
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))
    def panel(method, path, token=None, body=None):
        req = urllib.request.Request('http://127.0.0.1:8180/api/v1'+path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Content-Type':'application/json', **({'Authorization':'Bearer '+token} if token else {})})
        try:
            with opener.open(req, timeout=30) as r:
                data = json.load(r)
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and token:
                invalidate(token)
            raise
        if data.get('code') != 0:
            raise RuntimeError('Panel error')
        return data['data']
    if panel_override is not None:
        panel = panel_override
    authenticate = (lambda credentials: panel('POST','/auth/login',body=credentials)['access_token']) if panel_override is not None else (lambda credentials: login(panel, credentials))
    admin = authenticate(config['admin']) if account_snapshot is None else None
    user = authenticate(config['partner'])
    now = time.time() if now_override is None else now_override
    try:
        previous = json.loads(Path(config['snapshot_path']).read_text()).get('accounts', [])
    except (OSError, ValueError, KeyError):
        previous = []
    previous = {a['label']: a for a in previous if isinstance(a, dict) and 'label' in a}
    accounts = []
    for key, label in (config['accounts'].items() if account_snapshot is None else []):
        account = panel('GET', '/admin/accounts/'+key, admin)
        old = previous.get(label, {})
        view = account_view(account, label, now)
        try:
            if old.get('next_retry_at', 0) > now:
                raise RuntimeError('Quota query is in cooldown')
            # Queries the quota endpoint only. Never generates text or redeems reset credits.
            quota = panel('POST', '/admin/openai/accounts/'+key+'/quota/refresh', admin, {})
            view = quota_view(account, label, quota, now)
        except Exception as exc:
            # Keep historical data without pretending that this poll refreshed it.
            if (epoch(old.get('snapshot_at')) or 0) > (epoch(view.get('snapshot_at')) or 0):
                view = {**old, 'status': account.get('status'), 'schedulable': account.get('schedulable') is True}
            view = {**view, 'snapshot_stale': True, 'last_attempt_at': now,
                    'refresh_error': '上游额度查询失败，保留历史记录；稍后自动重试'}
            cooldown = 300 if isinstance(exc, urllib.error.HTTPError) and exc.code == 429 else 60
            view['next_retry_at'] = max(old.get('next_retry_at', 0), now+cooldown) if not isinstance(exc, RuntimeError) else old.get('next_retry_at', now+60)
            view['windows'] = [{**w, 'stale': True} for w in view.get('windows', [])]
        accounts.append(view)
    if account_snapshot is not None:
        accounts = account_snapshot
    end = time.strftime('%Y-%m-%d', time.gmtime(now))
    stats = panel('GET','/usage/stats?start_date=2000-01-01&end_date='+end+'&timezone=UTC',user)
    records = panel('GET','/usage?page=1&page_size=30',user)['items']
    return {'generated_at': now, 'quota_refresh_interval_seconds': 60, 'accounts':accounts,
            'totals':{k:stats.get(k) for k in ['total_requests','total_tokens','total_input_tokens','total_output_tokens','total_cache_read_tokens']},
            'records':[record_view(r,config['accounts'],config['groups']) for r in records]}


def main():
    import grp
    config=json.loads(Path(sys.argv[1]).read_text())
    dest=Path(config['snapshot_path'])
    failed=False
    try:
        data=collect(config)
    except Exception:
        failed=True
        try:data=json.loads(dest.read_text())
        except (OSError,ValueError):data={'generated_at':None,'accounts':[],'totals':{},'records':[]}
        data.update(error='后台用量同步暂时失败，保留上次记录',failed_at=time.time())
        data['accounts'] = [{**a, 'snapshot_stale': True,
                             'windows': [{**w, 'stale': True} for w in a.get('windows', [])]}
                            for a in data.get('accounts', [])]
    tmp=dest.with_suffix('.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o640)
    with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False)
    os.chown(tmp,0,grp.getgrnam('tokenbot-bridge').gr_gid)
    os.chmod(tmp,0o640);tmp.replace(dest)
    print('Partner snapshot failed; continuing independent customers.' if failed else 'Sanitized partner usage snapshot updated.')
    # Each customer authenticates as its own non-admin upstream user. Never filter a
    # global usage dump client-side, and never query quota again for every customer.
    for file in sorted(Path(config['customers_dir']).glob('*.json')) if config.get('customers_dir') else []:
        customer=json.loads(file.read_text())
        if not customer.get('snapshot_path'):
            continue  # Incomplete provisioning recovery record.
        target=Path(customer['snapshot_path'])
        try:
            snapshot=collect(customer,account_snapshot=data['accounts'])
        except Exception:
            failed=True
            try:snapshot=json.loads(target.read_text())
            except (OSError,ValueError):snapshot={'generated_at':None,'accounts':[],'totals':{},'records':[]}
            snapshot.update(error='客户用量同步失败，保留历史记录',failed_at=time.time())
        temp=target.with_suffix('.tmp')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o640)
        with os.fdopen(fd,'w') as f:json.dump(snapshot,f,ensure_ascii=False)
        os.chown(temp,0,grp.getgrnam('tokenbot-bridge').gr_gid);os.chmod(temp,0o640);temp.replace(target)
    if failed:raise SystemExit('One or more usage snapshots failed; independent customers were still attempted.')


if __name__=='__main__':main()
