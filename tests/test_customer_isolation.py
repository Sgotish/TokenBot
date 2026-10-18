import copy
import json
import time

import httpx
from fastapi.testclient import TestClient
from tokenbot.partner_gateway import create_app, MODEL
from test_partner_portal import config


def fixture(tmp_path):
    cfg=config(tmp_path)
    registry=tmp_path/'clients.json'
    cfg['clients_path']=str(registry)
    clients={}
    for ident in ('alice','bob'):
        snapshot=tmp_path/(ident+'-usage.json')
        snapshot.write_text(json.dumps({'generated_at':time.time(),'accounts':[],
            'records':[{'marker':ident+'-private-record'}],'totals':{'total_requests':1 if ident=='alice' else 2}}))
        clients[ident]={'key':ident+'-secret','label':ident,'expires_at':None,
            'selection_path':str(tmp_path/(ident+'-selection.json')),'snapshot_path':str(snapshot),
            'pools':{p:{'label':p,'key':ident+'-'+p+'-upstream'} for p in ('auto','plus','pro')}}
    registry.write_text(json.dumps({'clients':clients}))
    return cfg,registry,clients


def test_customer_keys_cookies_pool_choices_and_records_are_isolated(tmp_path):
    cfg,file,clients=fixture(tmp_path);sent=[]
    def upstream(request):
        sent.append(dict(request.headers));return httpx.Response(200,json={'ok':True})
    app=create_app(cfg,httpx.MockTransport(upstream))
    with TestClient(app,base_url=cfg['public_origin']) as a, TestClient(app,base_url=cfg['public_origin']) as b:
        for client,ident in ((a,'alice'),(b,'bob')):
            client.headers['origin']=cfg['public_origin']
            assert client.post('/portal/api/login',json={'key':clients[ident]['key']}).status_code==200
        assert a.post('/portal/api/pool',json={'pool':'plus'}).status_code==200
        assert b.post('/portal/api/pool',json={'pool':'pro'}).status_code==200
        for client,ident,pool in ((a,'alice','plus'),(b,'bob','pro')):
            r=client.get('/v1/usage');assert r.status_code==200
            assert r.json()['selected_pool']==pool
            assert ident+'-private-record' in r.text
            assert ('bob' if ident=='alice' else 'alice')+'-private-record' not in r.text
            assert 'secret' not in r.text and 'upstream' not in r.text
            assert client.post('/v1/responses',json={'model':MODEL,'input':'hello'},headers={'session_id':'same'}).status_code==200
            assert sent[-1]['authorization']=='Bearer '+clients[ident]['pools'][pool]['key']
        assert sent[0]['session_id']!=sent[1]['session_id']
        assert app.state.pool_state.selected=='auto'
        # A bad bearer must never fall back to the valid browser cookie.
        assert a.get('/v1/usage',headers={'authorization':'Bearer wrong'}).status_code==401
        clients['alice']['enabled']=False;file.write_text(json.dumps({'clients':clients}))
        assert a.get('/v1/usage').status_code==401
        assert a.post('/v1/responses',json={'model':MODEL,'input':'hello'}).status_code==401
        assert b.get('/v1/usage').status_code==200
        assert b.post('/portal/api/pool',json={'pool':'auto'}).status_code==200


def test_rotation_invalidates_existing_cookie_and_old_key(tmp_path):
    cfg,file,clients=fixture(tmp_path)
    with TestClient(create_app(cfg),base_url=cfg['public_origin']) as c:
        c.headers['origin']=cfg['public_origin']
        assert c.post('/portal/api/login',json={'key':'alice-secret'}).status_code==200
        clients['alice']['key']='rotated-alice-secret';file.write_text(json.dumps({'clients':clients}))
        assert c.get('/v1/usage').status_code==401
        assert c.get('/v1/usage',headers={'authorization':'Bearer alice-secret'}).status_code==401
        assert c.get('/v1/usage',headers={'authorization':'Bearer rotated-alice-secret'}).status_code==200
        clients['alice']['expires_at']=time.time()-1;file.write_text(json.dumps({'clients':clients}))
        assert c.get('/v1/usage',headers={'authorization':'Bearer rotated-alice-secret'}).status_code==401


def test_aliases_and_malformed_registry_fail_closed(tmp_path):
    cfg,file,clients=fixture(tmp_path)
    with TestClient(create_app(cfg),base_url=cfg['public_origin']) as c:
        for field in ('key','selection_path','snapshot_path','pools'):
            broken=copy.deepcopy(clients);broken['bob'][field]=broken['alice'][field]
            file.write_text(json.dumps({'clients':broken}))
            assert c.get('/v1/usage',headers={'authorization':'Bearer alice-secret'}).status_code==401
        file.write_text('{invalid')
        assert c.get('/v1/usage',headers={'authorization':'Bearer alice-secret'}).status_code==401
