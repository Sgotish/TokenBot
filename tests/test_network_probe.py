import asyncio
import json
import time
import httpx
from scripts.run_network_probe import create_app


def test_fixed_probe_budget_and_stream_without_key_disclosure():
    async def scenario():
        calls=[]
        async def upstream(req):
            calls.append(req)
            return httpx.Response(200,headers={'Content-Type':'text/event-stream'},content=(
                'data: {"type":"response.output_text.delta","delta":"42"}\n\n'
                'data: {"type":"response.completed","response":{"status":"completed","usage":{"input_tokens":1,"output_tokens":1}}}\n\n').encode())
        cfg={'key':'synthetic-secret','expires_at':time.time()+60,'cases':{'random-cap':{'mode':'answer','label':'test'}}}
        app=create_app(cfg,httpx.MockTransport(upstream))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            assert (await c.get('/network-check/random-cap?prompt=anything')).status_code==404
            assert (await c.get('/network-check/unknown')).status_code==404
            r=await c.get('/network-check/random-cap')
            assert '"pass": true' in r.text and '"upstream_completed": true' in r.text
            assert cfg['key'] not in r.text
            assert (await c.get('/network-check/random-cap')).status_code==404
            assert len(calls)==1 and json.loads(calls[0].content)['model']=='gpt-6.1-sol'
    asyncio.run(scenario())


def test_probe_expiry_and_failed_response_do_not_retry():
    async def scenario():
        calls=[]
        def upstream(req):calls.append(req);return httpx.Response(429)
        cfg={'key':'synthetic-secret','expires_at':time.time()+60,'cases':{'cap':{'mode':'answer','label':'test'}}}
        app=create_app(cfg,httpx.MockTransport(upstream))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            assert '"http": 429' in (await c.get('/network-check/cap')).text
            assert (await c.get('/network-check/cap')).status_code==404
            assert len(calls)==1
        cfg['expires_at']=time.time()-1
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            assert (await c.get('/network-check/cap')).status_code==404
    asyncio.run(scenario())


def test_globalping_assessment_rejects_wrong_network_and_incomplete_stream():
    from copy import deepcopy
    from scripts.run_guangdong_probes import assess
    body = ('event: text\ndata: {"delta":"42"}\n\n'
            'event: completed\ndata: {"pass":true,"upstream_completed":true}\n\n')
    report = {'status':'finished','results':[{'probe':{'country':'CN','city':'Guangzhou','asn':4134},
              'result':{'status':'finished','statusCode':200,'truncated':False,
                        'tls':{'authorized':True},'rawBody':body}}]}
    assert assess(report, 'Guangzhou', 'answer')['pass']
    bad = deepcopy(report); bad['results'][0]['probe']['city']='Shanghai'
    assert not assess(bad, 'Guangzhou', 'answer')['pass']
    for field, value in [('truncated',True),('rawBody','event: text\ndata: {"delta":"42"}\n\n'),
                         ('tls',{'authorized':False}),('status','failed')]:
        bad=deepcopy(report);bad['results'][0]['result'][field]=value
        assert not assess(bad,'Guangzhou','answer')['pass']
    stream=deepcopy(report)
    expected='\n'.join(map(str,range(1,81)))+'\nEND-GD'
    stream['results'][0]['result']['rawBody']='event: text\ndata: '+json.dumps({'delta':expected})+'\n\nevent: completed\ndata: '+json.dumps({'pass':True,'upstream_completed':True,'total_seconds':20.001})+'\n\n'
    stream['results'][0]['result']['timings']={'total':20900}
    assert assess(stream,'Guangzhou','stream')['pass']
    stream['results'][0]['result']['timings']['total']=1000
    assert not assess(stream,'Guangzhou','stream')['pass']
