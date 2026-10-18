import json
import time
from datetime import datetime, timezone
import httpx
from fastapi.testclient import TestClient
from tokenbot.partner_gateway import create_app, MODEL
from tokenbot.partner_portal import PoolState
from tokenbot.usage_snapshot import account_view, record_view


def config(tmp_path):
    snapshot=tmp_path/'status.json'
    snapshot.write_text(json.dumps({'generated_at':time.time(),'accounts':[],'records':[],'totals':{}}))
    return {'key':'public-partner-key','expires_at':None,'max_concurrency':2,'allowed_ips':['testclient'],
            'public_origin':'https://partner.test','selection_path':str(tmp_path/'selection.json'),'snapshot_path':str(snapshot),
            'pools':{'auto':{'key':'public-partner-key','label':'Auto'},'plus':{'key':'internal-plus-secret','label':'Plus'},'pro':{'key':'internal-pro-secret','label':'Pro'}}}


def test_portal_auth_csrf_private_keys_and_persistent_routing(tmp_path):
    cfg=config(tmp_path);sent=[]
    def upstream(request):
        sent.append(request.headers['authorization'])
        return httpx.Response(200,json={'ok':True})
    app=create_app(cfg,httpx.MockTransport(upstream))
    with TestClient(app,base_url='https://partner.test') as c:
        assert c.get('/portal').status_code==200
        assert "frame-ancestors 'none'" in c.get('/portal').headers['content-security-policy']
        assert c.get('/portal/api/status').status_code==401
        assert c.post('/portal/api/login',json={'key':cfg['key']}).status_code==403
        c.headers['origin']=cfg['public_origin']
        assert c.post('/portal/api/login',json={'key':'wrong'}).status_code==401
        r=c.post('/portal/api/login',json={'key':cfg['key']});assert r.status_code==200
        assert 'HttpOnly' in r.headers['set-cookie'] and 'Secure' in r.headers['set-cookie']
        for pool in ['plus','pro','auto']:
            assert c.post('/portal/api/pool',json={'pool':pool}).status_code==200
            r=c.post('/v1/responses',json={'model':MODEL,'input':'hi'})
            assert r.status_code==200 and r.headers['x-tokenbot-pool']==pool
            assert sent[-1]=='Bearer '+cfg['pools'][pool]['key']
            assert PoolState(cfg).selected==pool
        assert c.post('/portal/api/pool',json={'pool':'untrusted'}).status_code==400
        app.state.pool_state.active=1
        assert c.post('/portal/api/pool',json={'pool':'plus'}).status_code==409
        app.state.pool_state.active=0
        c.headers['origin']='https://evil.test'
        assert c.post('/portal/api/pool',json={'pool':'pro'}).status_code==403
        assert c.post('/v1/responses',json={'model':MODEL,'input':'hi'}).status_code==403
        status=c.get('/portal/api/status');assert status.status_code==200
        assert not any(secret in status.text for secret in ['internal-plus-secret','internal-pro-secret',cfg['key']])
        assert c.get('/api/v1/admin/accounts').status_code==404
        c.headers['origin']=cfg['public_origin'];assert c.post('/portal/api/logout',json={}).status_code==200
        assert c.get('/portal/api/status').status_code==401
        c.headers['authorization']='Bearer '+cfg['key']
        assert c.get('/v1/usage').status_code==200


def test_quota_does_not_invent_missing_or_expired_windows():
    now=time.time();stamp=datetime.fromtimestamp(now,timezone.utc).isoformat();future=datetime.fromtimestamp(now+3600,timezone.utc).isoformat()
    a={'status':'active','schedulable':True,'credentials':{'access_token':'never-export'},'extra':{'codex_usage_updated_at':stamp,'codex_7d_used_percent':6,'codex_7d_window_minutes':10080,'codex_7d_reset_at':future,'codex_5h_used_percent':0,'codex_5h_window_minutes':0}}
    d=account_view(a,'Pro',now)
    assert d['windows'][0]['remaining_percent'] is None
    assert d['windows'][1]['remaining_percent']==94
    assert 'never-export' not in json.dumps(d)
    assert account_view(a,'Pro',now+4000)['windows'][1]['remaining_percent'] is None
    assert account_view(a,'Pro',now+1000)['snapshot_stale'] is True
    a['extra']['codex_7d_used_percent']=float('nan')
    assert account_view(a,'Pro',now)['windows'][1]['remaining_percent'] is None


def test_domain_migration_accepts_only_explicit_https_origins(tmp_path):
    cfg = config(tmp_path)
    cfg['allowed_origins'] = ['https://legacy.test']
    with TestClient(create_app(cfg), base_url='https://partner.test') as client:
        for origin in ['https://partner.test', 'https://legacy.test']:
            assert client.post('/portal/api/login', headers={'origin': origin}, json={'key': cfg['key']}).status_code == 200
        for origin in ['https://evil.test', 'https://legacy.test.evil.test', 'http://legacy.test', 'null']:
            assert client.post('/portal/api/login', headers={'origin': origin}, json={'key': cfg['key']}).status_code == 403


def test_records_only_export_usage_fields():
    r={'account_id':1,'group_id':5,'input_tokens':10,'output_tokens':2,'cache_read_tokens':5,'user':{'email':'private'},'api_key':{'key':'secret'},'request_id':'internal','ip_address':'private'}
    out=record_view(r,{'1':'Pro'}, {'5':'Pro only'})
    assert out['total_tokens']==17 and out['account']=='Pro'
    assert 'private' not in json.dumps(out) and 'secret' not in json.dumps(out)
