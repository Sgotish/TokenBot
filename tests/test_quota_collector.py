import json
import urllib.error
from scripts.collect_partner_usage import collect


def test_parent_failure_does_not_skip_customers(tmp_path, monkeypatch):
    import grp, os, sys
    from types import SimpleNamespace
    from scripts import collect_partner_usage as module
    parent=tmp_path/'parent.json';parent.write_text(json.dumps({'generated_at':1,'accounts':[]}))
    customers=tmp_path/'customers';customers.mkdir()
    child=tmp_path/'child-status.json'
    (customers/'a.json').write_text(json.dumps({'snapshot_path':str(child),'partner':{}}))
    config=tmp_path/'config.json';config.write_text(json.dumps({'snapshot_path':str(parent),'customers_dir':str(customers)}))
    calls=[]
    def fake(cfg,**kwargs):
        calls.append(cfg)
        if cfg['snapshot_path']==str(parent):raise RuntimeError('parent unavailable')
        return {'generated_at':200,'accounts':[],'records':[{'id':1}]}
    monkeypatch.setattr(module,'collect',fake)
    monkeypatch.setattr(grp,'getgrnam',lambda _:SimpleNamespace(gr_gid=os.getgid()))
    monkeypatch.setattr(os,'chown',lambda *args:None)
    monkeypatch.setattr(sys,'argv',['collect',str(config)])
    import pytest
    with pytest.raises(SystemExit):module.main()
    assert len(calls)==2 and json.loads(child.read_text())['generated_at']==200


def test_customer_snapshot_uses_only_own_user_and_shared_sanitized_quota(tmp_path):
    calls=[]
    account=[{'label':'Pro','windows':[]}]
    def panel(method,path,token=None,body=None):
        calls.append(path)
        if path=='/auth/login':
            assert body=={'email':'customer@example.com','password':'synthetic'}
            return {'access_token':'customer'}
        assert token=='customer'
        if path.startswith('/usage/stats?start_date=2000-01-01&'):return {'total_requests':3,'secret':'not-exported'}
        if path.startswith('/usage?'):return {'items':[]}
        raise AssertionError('Customer collector must never access admin/quota endpoints')
    result=collect({'partner':{'email':'customer@example.com','password':'synthetic'},'accounts':{},
        'groups':{},'snapshot_path':str(tmp_path/'missing.json')},panel,1800000000,account_snapshot=account)
    assert result['accounts']==account and result['totals']['total_requests']==3
    assert 'not-exported' not in json.dumps(result)
    assert len(calls)==3


def test_collector_queries_quota_without_model_calls_and_retains_failure_history(tmp_path):
    now = 1800000000
    snapshot = tmp_path/'status.json'
    config = {'admin': {}, 'partner': {}, 'accounts': {'1':'Pro'}, 'groups': {}, 'snapshot_path': str(snapshot)}
    calls = []
    failed = False
    def panel(method, path, token=None, body=None):
        calls.append((method,path))
        if path == '/auth/login': return {'access_token':'synthetic'}
        if path == '/admin/accounts/1': return {'status':'active','schedulable':True,'extra':{}}
        if path.endswith('/quota/refresh'):
            if failed: raise urllib.error.HTTPError('http://localhost',429,'limited',{},None)
            return {'fetched_at': now, 'email':'never-export', 'rate_limit': {
                'primary_window': {'used_percent':21, 'limit_window_seconds':604800, 'reset_at':now+3600}}}
        if path.startswith('/usage/stats?start_date=2000-01-01&'): return {}
        if path.startswith('/usage?'): return {'items': []}
        raise AssertionError(path)
    first = collect(config,panel,now)
    account = first['accounts'][0]
    assert account['source'] == 'quota_api'
    assert account['windows'][0]['remaining_percent'] is None
    assert account['windows'][0]['resets_at'] is None
    assert account['windows'][1]['remaining_percent'] == 79
    assert 'never-export' not in json.dumps(first)
    snapshot.write_text(json.dumps(first))
    failed = True
    second = collect(config,panel,now+60)
    stale = second['accounts'][0]
    assert stale['snapshot_at'] == account['snapshot_at']
    assert stale['snapshot_stale'] is True and stale['refresh_error']
    assert stale['windows'][1]['remaining_percent'] == 79
    assert stale['next_retry_at'] == now+360
    snapshot.write_text(json.dumps(second))
    calls.clear()
    third = collect(config,panel,now+120)
    assert not any('/quota/refresh' in p for _,p in calls)
    assert third['accounts'][0]['next_retry_at'] == now+360
    assert not any('/responses' in p or 'reset-quota' in p for _,p in calls)
