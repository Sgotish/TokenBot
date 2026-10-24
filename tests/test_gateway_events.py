import json
from contextlib import contextmanager
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from tokenbot.gateway_events import record_failure, recent_failures
from tokenbot.partner_gateway import create_app
from tokenbot.partner_portal import PoolState


def test_guard_failure_is_scoped_visible_and_releases_capacity(tmp_path):
    registry=tmp_path/'clients.json';registry.write_text('{"clients":{}}')
    cfg={'key':'private-key','expires_at':None,'allowed_ips':['testclient'],
         'clients_path':str(registry),'selection_path':str(tmp_path/'selection.json')}
    calls=[]
    def upstream(r):
        calls.append(r);return httpx.Response(200,json={'ok':True})
    @contextmanager
    def unavailable(*a,**kw):
        raise OSError(30,'Read-only file system');yield
    with TestClient(create_app(cfg,httpx.MockTransport(upstream))) as c:
        c.headers['authorization']='Bearer private-key'
        with patch('tokenbot.partner_gateway.pricing_lock',unavailable):
            r=c.post('/v1/responses',json={'model':'gpt-6.1-sol','input':'secret prompt'})
        assert r.status_code==503 and not calls
        events=PoolState(cfg).status()['recent_failures']
        assert events[0]['request_id']==r.headers['x-request-id']
        assert events[0]['not_forwarded'] and events[0]['error_code']=='billing_guard'
        assert 'secret' not in json.dumps(events) and 'private-key' not in json.dumps(events)
        assert c.post('/v1/responses',json={'model':'gpt-6.1-sol','input':'hello'}).status_code==200
        assert len(calls)==1
    other=tmp_path/'other';other.mkdir()
    assert recent_failures({'selection_path':str(other/'selection.json')})==[]


def test_failure_log_retention_survives_restarts_and_bad_file(tmp_path):
    cfg={'selection_path':str(tmp_path/'selection.json')}
    for i in range(105):record_failure(cfg,'gpt-6.1-sol',503,'billing_guard',.1)
    assert len(recent_failures(cfg))==100
    (tmp_path/'gateway-failures.json').write_text('not json')
    assert PoolState({**cfg,'key':'a','expires_at':None}).status()['failures_unavailable']
    record_failure(cfg,'gpt-6.1-sol',409,'billing_guard',.1)
    assert len(recent_failures(cfg))==1


def test_free_test_requires_explicit_authorization_when_billing_is_live(tmp_path):
    path=tmp_path/'clients.json'
    cfg={'key':'owner-key','expires_at':None,'allowed_ips':['testclient'],'clients_path':str(path)}
    customer={'key':'customer-key','expires_at':None,'selection_path':str(tmp_path/'selection.json'),'snapshot_path':str(tmp_path/'snapshot.json')}
    data={'billing_live':True,'clients':{'web-'+'a'*32:customer}}
    path.write_text(json.dumps(data))
    calls=[]
    with TestClient(create_app(cfg,httpx.MockTransport(lambda r:(calls.append(r) or httpx.Response(200,json={'ok':True}))))) as c:
        c.headers['authorization']='Bearer customer-key'
        body={'model':'gpt-6.1-sol','input':'hello'}
        assert c.post('/v1/responses',json=body).status_code==403 and not calls
        customer['free_test_authorized']=True;path.write_text(json.dumps(data))
        assert c.post('/v1/responses',json=body).status_code==200 and len(calls)==1
