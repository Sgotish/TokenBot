#!/usr/bin/env python3
"""Outbound-only owner smoke tests. Never forwards subscription credentials to the site."""
import fcntl
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://tokenbots.top'
LOCAL = 'http://127.0.0.1:8180'
MODEL = 'gpt-6.1-sol'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def post(url, data, token=None):
    return OPENER.open(urllib.request.Request(url, data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json',
                 **({'Authorization': 'Bearer ' + token} if token else {})}), timeout=30)


def run_job(target):
    local = json.loads((ROOT / '.runtime/local.json').read_text())
    with post(LOCAL + '/api/v1/auth/login', {'email': local['admin_email'],
              'password': local['admin_password']}) as r:
        auth = json.load(r)['data']['access_token']
    account_id = {'pro': 1, 'plus': 2}[target]
    # Ensure a different provider or a new API-key account has not replaced the fixture.
    req = urllib.request.Request(LOCAL + '/api/v1/admin/accounts/' + str(account_id),
                                headers={'Authorization': 'Bearer ' + auth})
    with OPENER.open(req, timeout=15) as r:
        account = json.load(r)['data']
    if account['platform'] != 'openai' or account['type'] != 'oauth' or account['status'] != 'active':
        return 'failed', '本机账号类型或状态不符合本次订阅测试。'
    output, done, count = '', False, 0
    start = time.monotonic()
    with post(LOCAL + '/api/v1/admin/accounts/' + str(account_id) + '/test',
              {'model_id': MODEL, 'prompt': '', 'mode': 'default'}, auth) as response:
        for line in response:
            count += len(line)
            if count > 1048576 or time.monotonic() - start > 90:
                return 'unknown', '响应超过测试预算；未自动重试。'
            if not line.startswith(b'data:'):
                continue
            event = json.loads(line[5:].strip())
            if event.get('type') == 'content':
                output = (output + str(event.get('text', '')))[:2000]
            if event.get('type') == 'error':
                return 'failed', '订阅调用失败，请在本机后台核对；未自动重试。'
            if event.get('type') == 'test_complete':
                done = event.get('success') is True
    if not done or not output.strip():
        return 'unknown', '未收到完整成功事件及文本；未自动重试。'
    return 'completed', output


def main():
    os.umask(0o077)
    cfg = json.loads((ROOT / '.runtime/site-pilot.json').read_text())
    token = cfg['worker_token']
    lock = (ROOT / '.runtime/site-pilot.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    receipt = ROOT / '.runtime/site-pilot-receipts.json'
    seen = json.loads(receipt.read_text()) if receipt.exists() else {}
    def persist():
        temp = receipt.with_suffix('.tmp')
        temp.write_text(json.dumps(seen))
        temp.replace(receipt)
    print('Owner pilot worker started; outbound HTTPS only.', flush=True)
    while time.time() < cfg['expires_at']:
        try:
            with post(BASE + '/api/pilot/worker/claim', {}, token) as r:
                job = json.load(r).get('job')
            if job:
                jid = job.get('id', '')
                if (not re.fullmatch(r'[a-f0-9]{32}', jid) or job.get('target') not in ('pro', 'plus')
                        or job.get('model') != MODEL or time.time() - job['created_at'] > 180):
                    raise ValueError('Invalid job')
                if jid not in seen:
                    seen[jid] = {'status': 'unknown', 'output': '任务曾启动；若进程中断，不自动重新调用。'}
                    persist()  # Persist before consuming any subscription usage.
                    try:
                        status, output = run_job(job['target'])
                    except Exception:
                        status, output = 'unknown', '连接中断或调用异常，结果未知；未自动重试。'
                    seen[jid] = {'status': status, 'output': output}
                    persist()
                with post(BASE + '/api/pilot/worker/result', {'id': jid, **seen[jid]}, token) as r:
                    r.read(1024)
                print('Pilot job: ' + seen[jid]['status'], flush=True)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                print('Worker authorization rejected; stopped.', flush=True)
                break
        except Exception:
            pass  # No credential-bearing response or exception is logged.
        time.sleep(3)
    print('Pilot worker stopped.', flush=True)


if __name__ == '__main__':
    main()
