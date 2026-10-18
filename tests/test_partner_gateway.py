import time
import httpx
import json
import zstandard
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
        compressed=zstandard.ZstdCompressor().compress(json.dumps({'model':MODEL,'input':'hi'}).encode())
        assert c.post('/v1/responses',content=compressed,headers={'content-encoding':'zstd'}).status_code==200
        assert json.loads(calls[-1].content)['model']==MODEL
        bomb=zstandard.ZstdCompressor().compress(b'x'*(2*1024*1024+1))
        assert c.post('/v1/responses',content=bomb,headers={'content-encoding':'zstd'}).status_code==413
        assert c.get('/v1/models?client_version=0.162').status_code==200
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


def test_cloud_trial_has_no_expiry_but_still_requires_key():
    cfg={'expires_at':None,'allowed_ips':['testclient'],'key':'synthetic-cloud-key','max_concurrency':2}
    def upstream(request):
        return httpx.Response(200,json={'ok':True})
    with TestClient(create_app(cfg,httpx.MockTransport(upstream))) as c:
        assert c.get('/v1/models').status_code==401
        c.headers['authorization']='Bearer synthetic-cloud-key'
        assert c.post('/v1/responses',json={'model':MODEL,'input':'hi'}).status_code==200
        assert c.get('/api/v1/admin/accounts').status_code==404
        cfg['expires_at']=0
        assert c.get('/v1/models').status_code==403


def test_cloud_concurrency_releases_slots_after_completion():
    import asyncio

    async def scenario():
        entered = 0
        both_entered = asyncio.Event()
        finish = asyncio.Event()

        async def upstream(request):
            nonlocal entered
            entered += 1
            if entered == 2:
                both_entered.set()
            await finish.wait()
            return httpx.Response(200, json={'ok': True})

        cfg = {'expires_at': None, 'allowed_ips': ['127.0.0.1'],
               'key': 'synthetic-cloud-key', 'max_concurrency': 2, 'max_pending': 0}
        app = create_app(cfg, httpx.MockTransport(upstream))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                    base_url='http://trial', headers={'authorization': 'Bearer synthetic-cloud-key'}) as c:
                async def call():
                    return await c.post('/v1/responses', json={'model': MODEL, 'input': 'hi'})
                first, second = asyncio.create_task(call()), asyncio.create_task(call())
                try:
                    await asyncio.wait_for(both_entered.wait(), 2)
                    busy = await call()
                    assert busy.status_code == 503 and busy.headers['retry-after'] == '5'
                    assert busy.headers['x-tokenbot-error-source'] == 'bridge_capacity'
                finally:
                    finish.set()
                assert [r.status_code for r in await asyncio.gather(first, second)] == [200, 200]
                assert (await call()).status_code == 200

    asyncio.run(scenario())


def test_session_affinity_and_retry_metadata_are_preserved_without_credentials():
    def upstream(request):
        assert request.headers['session_id'] == 'synthetic-session'
        assert request.headers['authorization'] == 'Bearer internal-test-key'
        assert 'cookie' not in request.headers
        assert 'x-secret' not in request.headers
        return httpx.Response(429, json={'error':'limited'}, headers={
            'retry-after':'30', 'x-request-id':'synthetic-id', 'set-cookie':'never-forward'})
    cfg = {'expires_at':None,'allowed_ips':['testclient'],'key':'public-test-key',
           'pools':{'auto':{'key':'internal-test-key','label':'Auto'}}}
    with TestClient(create_app(cfg,httpx.MockTransport(upstream))) as c:
        r=c.post('/v1/responses',json={'model':MODEL,'input':'hi'},headers={
            'Authorization':'Bearer public-test-key','session_id':'synthetic-session',
            'Cookie':'private=secret','X-Secret':'private'})
        assert r.status_code == 429 and r.headers['retry-after'] == '30'
        assert r.headers['x-request-id'] == 'synthetic-id'
        assert r.headers['x-tokenbot-error-source'] == 'upstream_gateway'
        assert 'set-cookie' not in r.headers


def test_burst_waits_without_quota_error_and_cancelled_queue_does_not_run():
    import asyncio
    async def scenario():
        entered=asyncio.Event();finish=asyncio.Event();calls=[]
        async def upstream(request):
            calls.append(request)
            entered.set()
            await finish.wait()
            return httpx.Response(200,json={'ok':True})
        cfg={'expires_at':None,'allowed_ips':['127.0.0.1'],'key':'synthetic',
             'max_concurrency':1,'max_pending':1,'queue_timeout_seconds':2}
        app=create_app(cfg,httpx.MockTransport(upstream))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'authorization':'Bearer synthetic'}) as c:
                async def call():return await c.post('/v1/responses',json={'model':MODEL,'input':'hi'})
                first=asyncio.create_task(call());await entered.wait()
                cancelled=asyncio.create_task(call())
                while app.state.pool_state.pending!=1:await asyncio.sleep(.001)
                overflow=await call();assert overflow.status_code==503 and overflow.headers['retry-after']=='5'
                try:app.state.pool_state.select('auto');assert False,'Must not switch with queued requests'
                except RuntimeError:pass
                cancelled.cancel()
                try:await cancelled
                except asyncio.CancelledError:pass
                assert app.state.pool_state.pending==0 and len(calls)==1
                queued=asyncio.create_task(call())
                while app.state.pool_state.pending!=1:await asyncio.sleep(.001)
                await asyncio.sleep(.02);finish.set()
                results=await asyncio.gather(first,queued)
                assert all(r.status_code==200 for r in results)
                assert int(results[1].headers['x-tokenbot-queue-wait-ms'])>=10
                assert len(calls)==2 and app.state.pool_state.pending==0 and app.state.pool_state.active==0
    asyncio.run(scenario())


def test_queue_timeout_reports_server_capacity_without_upstream_execution():
    import asyncio
    async def scenario():
        entered=asyncio.Event();finish=asyncio.Event();calls=[]
        async def upstream(request):
            calls.append(request);entered.set();await finish.wait()
            return httpx.Response(200,json={'ok':True})
        cfg={'expires_at':None,'allowed_ips':['127.0.0.1'],'key':'synthetic',
             'max_concurrency':1,'max_pending':1,'queue_timeout_seconds':.05}
        app=create_app(cfg,httpx.MockTransport(upstream))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'authorization':'Bearer synthetic'}) as c:
                async def call():return await c.post('/v1/responses',json={'model':MODEL,'input':'hi'})
                first=asyncio.create_task(call());await entered.wait()
                r=await call()
                assert r.status_code==503 and r.headers['x-tokenbot-error-source']=='bridge_capacity'
                assert len(calls)==1 and app.state.pool_state.pending==0
                finish.set();await first
                assert (await call()).status_code==200
    asyncio.run(scenario())


def test_portal_security_middleware_preserves_queued_http_disconnect(tmp_path):
    import asyncio
    async def scenario():
        entered=asyncio.Event();finish=asyncio.Event();disconnected=asyncio.Event();calls=[]
        async def upstream(request):
            calls.append(request);entered.set();await finish.wait()
            return httpx.Response(200,json={'ok':True})
        cfg={'expires_at':None,'allowed_ips':['127.0.0.1'],'key':'synthetic',
             'public_origin':'https://test','snapshot_path':str(tmp_path/'missing.json'),
             'max_concurrency':1,'max_pending':1,'queue_timeout_seconds':2}
        app=create_app(cfg,httpx.MockTransport(upstream))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://test',headers={'authorization':'Bearer synthetic'}) as c:
                first=asyncio.create_task(c.post('/v1/responses',json={'model':MODEL,'input':'hi'}));await entered.wait()
                sent_body=False;messages=[]
                async def receive():
                    nonlocal sent_body
                    if not sent_body:
                        sent_body=True
                        return {'type':'http.request','body':json.dumps({'model':MODEL,'input':'cancel before execution'}).encode(),'more_body':False}
                    if disconnected.is_set():return {'type':'http.disconnect'}
                    await disconnected.wait();return {'type':'http.disconnect'}
                async def send(message):messages.append(message)
                scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST',
                       'scheme':'https','path':'/v1/responses','raw_path':b'/v1/responses','query_string':b'',
                       'headers':[(b'authorization',b'Bearer synthetic'),(b'content-type',b'application/json')],
                       'client':('127.0.0.1',1234),'server':('test',443)}
                queued=asyncio.create_task(app(scope,receive,send))
                while app.state.pool_state.pending!=1:await asyncio.sleep(.001)
                disconnected.set()
                await asyncio.wait_for(queued,.8)
                assert app.state.pool_state.pending==0 and len(calls)==1
                assert next(m for m in messages if m['type']=='http.response.start')['status']==499
                finish.set();await first
    asyncio.run(scenario())
