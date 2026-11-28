import hashlib
import json
from tokenbot.partner_portal import ClientRegistry
from test_customer_isolation import fixture


def test_alias_changes_keep_live_and_queued_state_but_revoke_immediately(tmp_path):
    cfg, path, clients = fixture(tmp_path)
    registry = ClientRegistry(cfg)
    state = registry.resolve(key='alice-secret')[1]
    state.active, state.pending = 1, 2
    clients['alice']['aliases'] = {'new': {'digest': hashlib.sha256(b'alias-secret').hexdigest(), 'enabled': True}}
    path.write_text(json.dumps({'clients': clients}))
    assert registry.resolve(key='alice-secret')[1] is state
    assert registry.resolve(key='alias-secret')[1] is state
    assert (state.active, state.pending) == (1, 2)
    clients['alice']['aliases']['new']['enabled'] = False
    path.write_text(json.dumps({'clients': clients}))
    assert registry.resolve(key='alias-secret') is None
    assert registry.resolve(key='alice-secret')[1] is state
    clients['alice']['enabled'] = False
    path.write_text(json.dumps({'clients': clients}))
    assert registry.resolve(key='alice-secret') is None


def test_refresh_after_queue_does_not_replace_state_identity(tmp_path):
    cfg, path, clients = fixture(tmp_path)
    registry = ClientRegistry(cfg)
    state = registry.resolve(key='alice-secret')[1]
    clients['alice']['billing'] = {'status': 'active'}
    path.write_text(json.dumps({'clients': clients}))
    assert registry.resolve(key='alice-secret')[1] is state
    assert state.config['billing']['status'] == 'active'
