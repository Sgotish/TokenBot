#!/usr/bin/env python3
"""Read complete admin ledger pages and reuse existing sanitized quota snapshots."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tokenbot.client import NoRedirect
from tokenbot.capacity_research import connect, usage_row, save_scan, save_quota, report, prune


def panel_client(deadline):
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))
    def panel(method, path, token=None, body=None):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Collection deadline')
        req = urllib.request.Request('http://127.0.0.1:8180/api/v1'+path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer '+token} if token else {})})
        with opener.open(req, timeout=min(10, remaining)) as response:
            raw = response.read(8*1024*1024+1)
        if len(raw) > 8*1024*1024:
            raise ValueError('Oversized panel response')
        data = json.loads(raw)
        if data.get('code') != 0:
            raise ValueError('Panel rejected request')
        return data['data']
    return panel


def fetch_usage(panel, token, start, end, max_pages=200):
    """No top-N truncation. Unstable pagination never advances coverage."""
    params = {'start_date': datetime.fromtimestamp(start, timezone.utc).strftime('%Y-%m-%d'),
              'end_date': datetime.fromtimestamp(end, timezone.utc).strftime('%Y-%m-%d'),
              'timezone': 'UTC', 'page_size': 100, 'exact_total': 'true',
              'sort_by': 'created_at', 'sort_order': 'asc'}
    rows, expected = {}, None
    for page in range(1, max_pages+1):
        result = panel('GET', '/admin/usage?'+urllib.parse.urlencode({**params, 'page': page}), token)
        count, items = result.get('total'), result.get('items')
        if type(count) is not int or count < 0 or not isinstance(items, list):
            raise ValueError('Unknown pagination contract')
        if expected is None:
            expected = count
        if count != expected:
            raise ValueError('Ledger changed during pagination; retry next poll')
        for item in items:
            row = usage_row(item)
            if row['id'] in rows:
                raise ValueError('Duplicate page record')
            rows[row['id']] = row
        if len(rows) == expected:
            # Check the count again even for a one-page scan.
            check = panel('GET', '/admin/usage?'+urllib.parse.urlencode({**params, 'page': 1, 'page_size': 1}), token)
            if check.get('total') != expected:
                raise ValueError('Ledger changed during pagination')
            return [r for r in rows.values() if start <= r['stamp'] <= end]
        if not items or len(rows) > expected:
            raise ValueError('Incomplete ledger page')
    raise ValueError('Ledger exceeds bounded scan; coverage not advanced')


def collect(db, config, panel, snapshot, now):
    save_quota(db, snapshot, config['accounts'], now)
    last = db.execute('SELECT MAX(end) FROM scans').fetchone()[0]
    # First run backfills 31 days; later polls overlap at least two days,
    # or backfill the entire downtime. Days are UTC as required by upstream.
    start = min(now-2*86400, last-86400) if last is not None else now-31*86400
    start = int(start//86400)*86400
    token = panel('POST', '/auth/login', body=config['admin'])['access_token']
    rows = fetch_usage(panel, token, start, now)
    # An admin scan sees all accounts; persist only the configured account pool.
    save_scan(db, [r for r in rows if r['account'] in config['accounts']], start, now, now)
    prune(db, now)


def write_report(path, data):
    temp = path.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    if os.name == 'posix':
        import grp
        os.chown(temp, 0, grp.getgrnam('tokenbot-bridge').gr_gid)
    os.chmod(temp, 0o640)
    temp.replace(path)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--collector', default='/opt/tokenbot-pilot/private/collector.json')
    parser.add_argument('--state', default='/var/lib/tokenbot-research')
    args = parser.parse_args()
    os.umask(0o077)
    config = json.loads(Path(args.collector).read_text(encoding='utf-8'))
    state = Path(args.state)
    now = time.time()
    with connect(state/'history.sqlite3') as db:
        failed = False
        try:
            snapshot = json.loads(Path(config['snapshot_path']).read_text(encoding='utf-8'))
            collect(db, config, panel_client(time.monotonic()+45), snapshot, now)
        except Exception:
            # Do not log URLs, responses, credentials, or raw upstream exceptions.
            failed = True
        data = report(db, config['accounts'], now)
        data['collection_failed'] = failed
        write_report(state/'report.json', data)
    if failed:
        raise SystemExit('Research collection incomplete; retained history, coverage not advanced.')
    print('Capacity research snapshot updated; no model requests or billing mutations.')


if __name__ == '__main__':
    main()
