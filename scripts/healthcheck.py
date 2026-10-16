#!/usr/bin/env python3
"""One non-billable local health probe. No account tokens, no automatic disable/re-enable."""
import argparse
import json
import time
import urllib.request
from urllib.parse import urlsplit
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8180/health');a=p.parse_args()
u=urlsplit(a.url)
if u.username or u.password or u.query or u.fragment or (u.scheme!='https' and u.hostname not in ('127.0.0.1','localhost')):
    p.error('Use HTTPS or loopback without credentials/query')
start=time.monotonic()
try:
    with urllib.request.urlopen(a.url,timeout=5) as r:
        ok=r.status==200 and json.load(r).get('status')=='ok'
except (OSError,ValueError):ok=False
print(json.dumps({'healthy':ok,'latency_ms':round((time.monotonic()-start)*1000),'checked_at_unix':time.time()}))
raise SystemExit(0 if ok else 1)
