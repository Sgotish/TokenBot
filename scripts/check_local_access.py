#!/usr/bin/env python3
"""Exercise the real empty local pilot. No external model request is allowed.

Creates a disposable ordinary user, exclusive empty group and expiring key.
Leaves audit records; disables these objects and clears synthetic balance at exit.
"""
import json
import os
from pathlib import Path
import secrets
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tokenbot.client import NoRedirect

BASE = 'http://127.0.0.1:8180'
OPENER = urllib.request.build_opener(NoRedirect())


def request(method, path, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json',
                 **({'Authorization': 'Bearer ' + token} if token else {})})
    try:
        with OPENER.open(req, timeout=20) as result:
            return result.status, json.load(result)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def panel(method, path, token=None, body=None):
    status, result = request(method, '/api/v1' + path, token, body)
    if status != 200 or result.get('code', 0) != 0:
        raise RuntimeError('Panel operation failed: ' + path + ' HTTP ' + str(status))
    return result['data']


def main():
    cfg = json.loads((ROOT / '.runtime/local.json').read_text())
    admin = panel('POST', '/auth/login', body={
        'email': cfg['admin_email'], 'password': cfg['admin_password']})['access_token']
    if panel('GET', '/admin/compliance', admin)['required']:
        raise RuntimeError('Operator must accept the agreement before testing')
    if panel('GET', '/admin/accounts', admin)['total'] != 0:
        raise RuntimeError('Refusing to run: upstream accounts exist; use a separate empty instance')
    nonce = secrets.token_hex(6)
    user = group = key = customer = None
    report = {'scope': 'real local HTTP, no upstream accounts or model execution', 'checks': {}}
    checks = report['checks']
    cleanup = []
    completed = False
    try:
        settings = panel('GET', '/admin/settings', admin)
        checks['registration_closed'] = settings['registration_enabled'] is False
        checks['payments_disabled'] = settings['payment_enabled'] is False
        group = panel('POST', '/admin/groups', admin, {
            'name': 'Access check ' + nonce, 'description': 'Empty disposable test group; not a customer plan',
            'platform': 'openai', 'rate_multiplier': 1, 'is_exclusive': True,
            'subscription_type': 'standard'})
        password = secrets.token_urlsafe(32)
        user = panel('POST', '/admin/users', admin, {
            'email': 'access-check-' + nonce + '@example.com', 'password': password,
            'username': 'Local access check', 'notes': 'Synthetic test; no customer or paid funds',
            'role': 'user', 'balance': 0, 'concurrency': 1, 'rpm_limit': 10,
            'allowed_groups': [group['id']], 'restrict_public_groups': True})
        customer = panel('POST', '/auth/login', body={
            'email': user['email'], 'password': password})['access_token']
        checks['ordinary_role'] = panel('GET', '/user/profile', customer)['role'] == 'user'
        status, _ = request('GET', '/api/v1/admin/users', customer)
        checks['admin_read_denied'] = status == 403
        status, _ = request('PUT', '/api/v1/admin/settings', customer, {'site_name': 'MUST NOT APPLY'})
        checks['admin_write_denied'] = status == 403
        checks['settings_preserved'] = panel('GET', '/admin/settings', admin)['site_name'] == settings['site_name']
        key = panel('POST', '/keys', customer, {
            'name': 'Disposable access check', 'group_id': group['id'], 'quota': 0.01,
            'expires_in_days': 1, 'ip_whitelist': ['127.0.0.1/32']})
        body = {'model': 'tokenbot-access-check-not-a-real-model', 'input': 'Synthetic access check',
                'max_output_tokens': 1, 'stream': False}
        status, _ = request('POST', '/v1/responses', key['key'], body)
        report['zero_balance_http_status'] = status
        checks['zero_balance_blocked'] = status in (402, 403)
        panel('POST', '/admin/users/' + str(user['id']) + '/balance', admin,
              {'balance': 1, 'operation': 'set', 'notes': 'Synthetic local test credit; no payment'})
        checks['synthetic_balance_visible'] = float(panel('GET', '/user/profile', customer)['balance']) == 1
        # Recheck immediately before request: this script must never consume upstream usage.
        if panel('GET', '/admin/accounts', admin)['total'] != 0:
            raise RuntimeError('Upstream account appeared; request skipped')
        status, _ = request('POST', '/v1/responses', key['key'], body)
        report['empty_pool_http_status'] = status
        checks['empty_pool_unavailable'] = status in (400, 503)
        after = panel('GET', '/user/profile', customer)
        checks['empty_pool_no_debit'] = float(after['balance']) == 1
        panel('PUT', '/keys/' + str(key['id']), customer, {'status': 'inactive'})
        status, _ = request('POST', '/v1/responses', key['key'], body)
        report['disabled_key_http_status'] = status
        checks['disabled_key_rejected'] = status in (401, 403)
        completed = True
    finally:
        if key and customer:
            try: panel('PUT', '/keys/' + str(key['id']), customer, {'status': 'inactive'})
            except Exception: cleanup.append('key disable failed')
        if user:
            try:
                path = '/admin/users/' + str(user['id'])
                balance = float(panel('GET', path, admin)['balance'])
                if balance > 0:
                    panel('POST', path + '/balance', admin,
                          {'balance': balance, 'operation': 'subtract', 'notes': 'Remove synthetic local test credit'})
                panel('PUT', path, admin, {'status': 'disabled'})
            except Exception: cleanup.append('user disable/zero balance failed')
        if group:
            try: panel('PUT', '/admin/groups/' + str(group['id']), admin, {'status': 'inactive'})
            except Exception: cleanup.append('group disable failed')
        report['cleanup_errors'] = cleanup
        report['passed'] = completed and bool(checks) and all(checks.values()) and not cleanup
        out = ROOT / 'reports/local-access-check.json'
        out.parent.mkdir(exist_ok=True, mode=0o700)
        fd = os.open(out, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f: json.dump(report, f, indent=2)
        print(json.dumps(report, indent=2))
    if not report['passed']: raise SystemExit(1)


if __name__ == '__main__':
    main()
