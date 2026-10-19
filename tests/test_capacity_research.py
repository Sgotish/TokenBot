from datetime import datetime, timezone
import json
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import pytest

from tokenbot.capacity_research import (TOKENS, connect, usage_row, save_scan, save_quota,
                                       measure, report, pricing, covered)
from tokenbot.research_app import create_app
from scripts.collect_capacity_research import fetch_usage, collect
from scripts.install_capacity_research import caddy_candidate, wait_for_auth_gate

BASE = 1800000000


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def raw(ident=1, stamp=BASE+900, model='sol', **kwargs):
    return {'id': ident, 'account_id': 1, 'created_at': iso(stamp), 'model': model,
            'reasoning_effort': 'low', 'service_tier': 'default', 'duration_ms': 1000,
            'input_tokens': 500000, 'output_tokens': 500000, 'cache_read_tokens': 1500000,
            'cache_creation_tokens': 0, **kwargs}


def quota(blocks=1):
    return [{'stamp': BASE+i*300, 'reset': BASE+604800, 'used': i*5/6}
            for i in range(6*blocks+1)]


def scans(end=BASE+86400):
    return [{'start': BASE-86400, 'end': end, 'collected': end}]


def test_counter_contract_no_double_cache_or_reasoning_count_and_no_private_data():
    r = usage_row(raw(reasoning_tokens=300000, api_key={'key': 'secret'}, ip_address='private', email='private'))
    assert sum(r[k] for k in TOKENS) == 2500000
    assert 'secret' not in json.dumps(r) and 'private' not in json.dumps(r)
    assert r['valid']
    assert not usage_row(raw(output_tokens=None))['valid']
    assert not usage_row(raw(input_tokens=True))['valid']
    assert not usage_row(raw(duration_ms=None))['valid']
    assert not usage_row(raw(image_count=1))['valid']
    assert not usage_row(raw(request_type='cyber'))['valid']


def test_passive_collection_deduplicates_usage_and_quota(tmp_path):
    db = connect(tmp_path/'history.db')
    now = BASE+2000
    snap = {'accounts': [{'label': 'Pro', 'source': 'quota_api', 'snapshot_at': iso(now),
            'windows': [{'label': '7 天窗口', 'remaining_percent': 90, 'resets_at': iso(now+1000)}]}]}
    calls = []
    def panel(method, path, token=None, body=None):
        calls.append(path)
        if path == '/auth/login': return {'access_token': 'private'}
        if path.startswith('/admin/usage?'): return {'total': 2, 'items': [raw(), raw(2, account_id=2)]}
        raise AssertionError(path)
    config = {'accounts': {'1': 'Pro'}, 'admin': {}}
    collect(db, config, panel, snap, now)
    collect(db, config, panel, snap, now)
    assert db.execute('SELECT COUNT(*) FROM usage').fetchone()[0] == 1
    assert db.execute('SELECT COUNT(*) FROM quota').fetchone()[0] == 1
    assert not any('refresh' in p or '/responses' in p for p in calls)
    assert 'private' not in json.dumps(report(db, config['accounts'], now))


def test_stale_unknown_and_duplicate_account_labels_do_not_become_measurements(tmp_path):
    db = connect(tmp_path/'history.db')
    for account in [
        {'label':'Pro', 'source':'quota_api', 'snapshot_at':iso(BASE-1000)},
        {'label':'Pro', 'source':'quota_api', 'snapshot_at':iso(BASE), 'snapshot_stale':True},
        {'label':'Pro', 'source':'legacy', 'snapshot_at':iso(BASE)},
    ]:
        account['windows'] = [{'label':'7 天窗口', 'remaining_percent':90, 'resets_at':iso(BASE+1000)}]
        save_quota(db, {'accounts':[account]}, {'1':'Pro'}, BASE)
    assert db.execute('SELECT COUNT(*) FROM quota').fetchone()[0] == 0


def test_mixed_models_never_receive_proportional_quota_attribution(tmp_path):
    db = connect(tmp_path/'history.db')
    save_scan(db, [usage_row(raw()), usage_row(raw(2, BASE+1000, 'astra'))], BASE-1000, BASE+3000, BASE+3000)
    with db:
        db.executemany('INSERT INTO quota VALUES (?,?,?,?,?)',
                       [('1',604800,q['stamp'],q['reset'],q['used']) for q in quota()])
    w = report(db, {'1':'Pro'}, BASE+3000)['accounts'][0]['windows'][1]
    assert len(w['estimates']) == 1 and w['estimates'][0]['cohort'] is None
    assert w['estimates'][0]['points_per_million'] == pytest.approx(1)


def test_same_model_different_effort_is_not_a_single_cohort():
    rows = [usage_row(raw()), usage_row(raw(2, BASE+1000, reasoning_effort='high'))]
    blocks, _ = measure(quota(), rows, scans(), BASE+4000)
    assert blocks[0]['cohort'] is None


def test_accumulated_zero_deltas_and_single_cohort_formula(tmp_path):
    db = connect(tmp_path/'history.db')
    rows = [usage_row(raw(i+1, BASE+900+i*1800)) for i in range(3)]
    save_scan(db, rows, BASE-86400, BASE+10000, BASE+10000)
    with db:
        db.executemany('INSERT INTO quota VALUES (?,?,?,?,?)',
            [('1',604800,q['stamp'],q['reset'],q['used']) for q in quota(3)])
    r = report(db, {'1':'Pro'}, BASE+10000)
    e = r['accounts'][0]['windows'][1]['estimates'][1]
    assert e['status'] == 'observed' and e['blocks'] == 3
    assert e['cohort'] == ['sol','low','default']
    assert e['points_per_million'] == pytest.approx(2)
    assert e['window_capacity_tokens'] == pytest.approx(50e6)
    assert e['monthly_capacity_tokens'] == pytest.approx(50e6*30/7)
    assert r['accounts'][0]['windows'][0]['estimates'] == []
    assert r['accounts'][0]['actual'][2]['complete'] is False
    p = pricing(e['monthly_capacity_tokens'],100,20,.7,.03,.3)
    assert p['sold_tokens_per_month'] == pytest.approx(150e6)
    assert p['break_even_per_million'] == pytest.approx(.824742268)
    assert p['target_per_million'] == pytest.approx(1.19402985)
    q = quota()
    for record in q[:-1]: record['used'] = 0
    blocks, _ = measure(q, [usage_row(raw())], scans(), BASE+4000)
    assert blocks[0]['points'] == pytest.approx(5)


@pytest.mark.parametrize('kind', ['reset','snapshot_gap','quota_decreased','ledger_gap','invalid_usage','quota_without_tokens','boundary_uncertainty'])
def test_invalid_intervals_do_not_produce_capacity(kind):
    q, r, s = quota(), [usage_row(raw())], scans()
    if kind == 'reset': q[-1]['reset'] += 604800
    if kind == 'snapshot_gap': q = [q[0], q[-1]]
    if kind == 'quota_decreased': q[-2]['used'] = 0
    if kind == 'ledger_gap': s = []
    if kind == 'invalid_usage': r[0]['valid'] = False
    if kind == 'quota_without_tokens': r = []
    if kind == 'boundary_uncertainty': r[0]['stamp'] = BASE+20
    blocks, rejected = measure(q, r, s, BASE+4000)
    assert not blocks and rejected[kind] == 1


def test_no_delta_and_unsettled_snapshot_cannot_create_free_capacity():
    q = quota()
    for record in q: record['used'] = 0
    assert measure(q, [usage_row(raw())], scans(), BASE+4000)[0] == []
    assert measure(quota(), [usage_row(raw())], scans(), BASE+1850)[0] == []


def test_complete_page_scan_and_missing_page_fail_closed():
    calls = []
    records = [raw(i+1) for i in range(205)]
    def panel(method,path,token=None):
        query = parse_qs(urlparse(path).query)
        page, size = int(query['page'][0]), int(query['page_size'][0])
        calls.append(page)
        return {'total':len(records), 'items':records[(page-1)*size:page*size]}
    assert len(fetch_usage(panel,'test',BASE,BASE+1000)) == 205
    assert calls == [1,2,3,1]
    with pytest.raises(ValueError, match='bounded'):
        fetch_usage(panel,'test',BASE,BASE+1000,max_pages=1)
    def missing(method,path,token=None):
        result = panel(method,path,token)
        if 'page=2' in path: result['items'] = []
        return result
    with pytest.raises(ValueError, match='Incomplete'):
        fetch_usage(missing,'test',BASE,BASE+1000)


def test_unstable_or_duplicate_pages_do_not_claim_coverage():
    count = 0
    def changing(method,path,token=None):
        nonlocal count
        count += 1
        return {'total':count, 'items':[raw()]}
    with pytest.raises(ValueError, match='changed'):
        fetch_usage(changing,'test',BASE,BASE+1000)
    def duplicate(method,path,token=None):
        return {'total':2, 'items':[raw()]}
    with pytest.raises(ValueError, match='Duplicate'):
        fetch_usage(duplicate,'test',BASE,BASE+1000)


def test_coverage_requires_gap_free_and_settled_scans():
    assert covered([{'start':0,'end':10,'collected':15},{'start':10,'end':20,'collected':25}],0,20)
    assert not covered([{'start':0,'end':9,'collected':15},{'start':10,'end':20,'collected':25}],0,20)
    assert not covered(scans(BASE+1800),BASE,BASE+1900,BASE+1900)


@pytest.mark.parametrize('args', [(0,100,0,.7,.03,.3),(1e6,100,0,0,.03,.3),(1e6,100,0,.7,.7,.3),(1e6,float('nan'),0,.7,.03,.3)])
def test_invalid_scenario_rejected(args):
    with pytest.raises(ValueError): pricing(*args)


def test_research_auth_is_separate_no_cors_or_secret_exposure(tmp_path):
    secret = 'synthetic-research-only-'+'x'*40
    (tmp_path/'report.json').write_text(json.dumps({'generated_at':1,'accounts':[]}))
    client = TestClient(create_app(tmp_path, secret))
    for headers in [{},{'Authorization':'Bearer customer-key'}]:
        result = client.get('/research/api/report', headers=headers)
        assert result.status_code == 401
        assert 'access-control-allow-origin' not in result.headers
    good = client.get('/research/api/report', headers={'Authorization':'Bearer '+secret})
    assert good.status_code == 200 and good.json()['report_stale']
    assert good.headers['cache-control'] == 'no-store'
    assert secret not in good.text
    assert client.get('/research').status_code == 200
    assert client.get('/research/assets/research.js').status_code == 200
    assert client.get('/research/assets/secret').status_code == 404
    assert client.post('/research/api/report',json={}).status_code == 405
    assert client.get('/docs').status_code == 404


def test_caddy_route_preserves_existing_control_plane_and_default():
    source = 'pilot.test {\n    reverse_proxy /internal/site/* 127.0.0.1:8184\n    reverse_proxy 127.0.0.1:8181\n}\n'
    candidate = caddy_candidate(source)
    assert 'reverse_proxy /internal/site/* 127.0.0.1:8184' in candidate
    assert 'reverse_proxy 127.0.0.1:8181' in candidate
    assert '@tokenbot_research path /research /research/*' in candidate
    assert caddy_candidate(candidate) == candidate
    with pytest.raises(ValueError): caddy_candidate('unrelated.test {respond 200}')
    with pytest.raises(ValueError): caddy_candidate('pilot.test {/research different}')


def test_installer_waits_for_listener_and_requires_authentication():
    import urllib.error
    class Starting:
        attempts = 0
        def open(self, endpoint, timeout):
            self.attempts += 1
            if self.attempts == 1:
                raise urllib.error.URLError('Connection refused')
            raise urllib.error.HTTPError(endpoint, 401, 'Unauthorized', {}, None)
    opener = Starting()
    wait_for_auth_gate(opener, 'http://localhost/research/api/report', pause=lambda _: None)
    assert opener.attempts == 2
    with pytest.raises(TimeoutError):
        wait_for_auth_gate(opener, 'http://localhost', timeout=0)
    class Public:
        def open(self, endpoint, timeout):
            from contextlib import nullcontext
            return nullcontext()
    with pytest.raises(RuntimeError, match='not rejected'):
        wait_for_auth_gate(Public(), 'http://localhost')
