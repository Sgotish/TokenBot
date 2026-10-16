import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.pilot_bridge import mount_pilot
from app.portal_store import PortalError

TOKEN = 'test-worker-secret-' * 4
WORKER = {'Authorization': 'Bearer ' + TOKEN}
OWNER = {'Origin': 'https://example.test', 'X-CSRF-Token': 'csrf-owner'}


class Store:
    def session(self, token):
        if token not in ('owner', 'other-admin', 'customer'):
            raise PortalError('login', 401)
        return {'id': token, 'role': 'customer' if token == 'customer' else 'admin',
                'csrf': 'csrf-' + token}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('PILOT_WORKER_TOKEN', TOKEN)
    monkeypatch.setenv('PILOT_ADMIN_USER_ID', 'owner')
    monkeypatch.setenv('PILOT_EXPIRES_AT', str(time.time() + 3600))
    app = FastAPI()
    app.state.portal = Store()
    mount_pilot(app, SimpleNamespace(public_origin='https://example.test'))
    with TestClient(app, base_url='https://example.test') as c:
        yield c


def owner(c):
    c.cookies.set('tb_session', 'owner')


def test_owner_only_and_expiry(client, monkeypatch):
    assert client.get('/api/pilot/status').status_code == 401
    for token in ('customer', 'other-admin'):
        client.cookies.set('tb_session', token)
        assert client.get('/api/pilot/status').status_code == 403
    owner(client)
    assert client.get('/api/pilot/status').status_code == 200
    monkeypatch.setenv('PILOT_EXPIRES_AT', '0')
    assert client.get('/api/pilot/status').status_code == 503
    assert client.post('/api/pilot/worker/claim', headers=WORKER, json={}).status_code == 503


def test_csrf_and_fixed_payload(client):
    owner(client)
    assert client.post('/api/pilot/run', json={'target': 'pro'}).status_code == 403
    assert client.post('/api/pilot/run', headers={**OWNER, 'Origin': 'https://evil.test'}, json={'target':'pro'}).status_code == 403
    for data in ({'target':'other'}, {'target':'pro','url':'http://localhost'}, {'target':'pro','prompt':'arbitrary'}):
        assert client.post('/api/pilot/run', headers=OWNER, json=data).status_code == 400


def test_worker_auth_and_disconnected(client):
    assert client.post('/api/pilot/worker/claim', json={}).status_code == 401
    owner(client)
    assert client.post('/api/pilot/run', headers=OWNER, json={'target':'pro'}).status_code == 503


def test_once_only_claim_result_and_bounded_output(client):
    owner(client)
    assert client.post('/api/pilot/worker/claim', headers=WORKER, json={}).json() == {'job': None}
    run = client.post('/api/pilot/run', headers=OWNER, json={'target':'pro'})
    assert run.status_code == 200
    jid = run.json()['id']
    job = client.post('/api/pilot/worker/claim', headers=WORKER, json={}).json()['job']
    assert job['id'] == jid and job['status'] == 'running'
    assert client.post('/api/pilot/worker/claim', headers=WORKER, json={}).json()['job'] is None
    assert client.post('/api/pilot/run', headers=OWNER, json={'target':'plus'}).status_code == 429
    data = {'id':jid,'status':'completed','output':'x'*2001}
    assert client.post('/api/pilot/worker/result', headers=WORKER, json=data).status_code == 400
    data['output'] = 'Synthetic test reply'
    assert client.post('/api/pilot/worker/result', headers=WORKER, json=data).status_code == 200
    assert client.post('/api/pilot/worker/result', headers=WORKER, json=data).status_code == 409
    assert client.get('/api/pilot/status').json()['jobs'][0]['output'] == data['output']


def test_timeout_never_requeues(client, monkeypatch):
    owner(client)
    client.post('/api/pilot/worker/claim', headers=WORKER, json={})
    client.post('/api/pilot/run', headers=OWNER, json={'target':'plus'})
    client.post('/api/pilot/worker/claim', headers=WORKER, json={})
    now = time.time()
    monkeypatch.setattr('app.pilot_bridge.time.time', lambda: now + 181)
    assert client.get('/api/pilot/status').json()['jobs'][0]['status'] == 'unknown'
    assert client.post('/api/pilot/worker/claim', headers=WORKER, json={}).json()['job'] is None


def test_body_and_url_bounds(client):
    owner(client)
    assert client.get('/api/pilot/status?token=bad').status_code == 400
    assert client.post('/api/pilot/run',headers=OWNER,json={'target':'x'*9000}).status_code == 413
