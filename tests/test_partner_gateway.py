import time
import httpx
from fastapi.testclient import TestClient
from tokenbot.partner_gateway import create_app, MODEL


def test_gateway_limits_auth_paths_and_preserves_stream():
    calls = []
    def upstream(request):
        calls.append(request)
        return httpx.Response(200, content=b'data: {"test":"synthetic"}\n\n', headers={'content-type':'text/event-stream'})
    cfg = {'expires_at':time.time()+60, 'allowed_ips':['testclient'], 'key':'synthetic-test-key'}
    with TestClient(create_app(cfg, httpx.MockTransport(upstream))) as c:
        assert c.get('/v1/models').status_code == 401
        c.headers['authorization'] = 'Bearer synthetic-test-key'
        for path in ('/admin/accounts','/api/v1/admin/users','/v1/responses/compact','/v1/models?token=x'):
            assert c.get(path).status_code == 404
        assert c.get('/v1/models').json()['data'][0]['id'] == MODEL
        assert c.post('/v1/responses',json={'model':'other'}).status_code == 400
        assert c.post('/v1/responses',json={'model':MODEL,'background':True}).status_code == 400
        assert c.post('/v1/responses',content=b'x'*(2*1024*1024+1)).status_code == 413
        r=c.post('/v1/responses',json={'model':MODEL,'input':'hi','stream':True})
        assert r.status_code==200 and r.content==b'data: {"test":"synthetic"}\n\n'
        assert len(calls)==1 and str(calls[0].url)=='http://127.0.0.1:8180/v1/responses'
        cfg['allowed_ips']=[]
        assert c.get('/v1/models').status_code==403
        cfg['allowed_ips']=['testclient'];cfg['expires_at']=0
        assert c.get('/v1/models').status_code==403


def test_redirect_is_not_followed_and_slot_is_released():
    calls=[]
    def upstream(request):
        calls.append(request)
        return httpx.Response(307,headers={'location':'https://example.invalid/steal'})
    cfg={'expires_at':time.time()+60,'allowed_ips':['testclient'],'key':'synthetic-test-key'}
    with TestClient(create_app(cfg,httpx.MockTransport(upstream))) as c:
        c.headers['authorization']='Bearer synthetic-test-key'
        for _ in range(2):
            assert c.post('/v1/responses',json={'model':MODEL,'input':'hi'}).status_code==502
    assert len(calls)==2
