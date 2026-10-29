import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from tokenbot.panel_session import login, invalidate


def test_reuses_access_only_and_separates_credentials(tmp_path):
    calls = []
    def panel(method, path, body):
        calls.append(body)
        return {'access_token': 'token-'+str(len(calls)), 'refresh_token': 'never-save', 'expires_in': 3600}
    a = {'email': 'a@example.test', 'password': 'secret-a'}
    b = {'email': 'b@example.test', 'password': 'secret-b'}
    assert login(panel,a,tmp_path,1000) == login(panel,a,tmp_path,1100)
    assert login(panel,b,tmp_path,1100) != login(panel,a,tmp_path,1100)
    assert len(calls) == 2
    for f in tmp_path.glob('*.json'):
        assert f.stat().st_mode & 0o777 == 0o600
        assert 'secret-' not in f.read_text() and 'never-save' not in f.read_text()
    assert login(panel,a,tmp_path,1901) == 'token-3'
    invalidate('token-3',tmp_path)
    assert login(panel,a,tmp_path,1910) == 'token-4'


def test_concurrent_logins_single_flight_and_failure_not_cached(tmp_path):
    calls=[]
    def panel(method,path,body):
        calls.append(body)
        return {'access_token':'synthetic','expires_in':120}
    with ThreadPoolExecutor(max_workers=5) as executor:
        assert list(executor.map(lambda _: login(panel,{},tmp_path,1000),range(5))) == ['synthetic']*5
    assert len(calls)==1
    def failed(*args,**kwargs):
        raise RuntimeError('offline')
    with pytest.raises(RuntimeError):login(failed,{},tmp_path,1061)
    assert login(panel,{},tmp_path,1062)=='synthetic'
    assert len(calls)==2


def test_missing_expiry_is_not_reused(tmp_path):
    calls=[]
    def panel(*args,**kwargs):
        calls.append(1);return {'access_token':'short'}
    login(panel,{},tmp_path,1000);login(panel,{},tmp_path,1001)
    assert len(calls)==2
