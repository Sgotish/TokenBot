"""Start the approved website release with the privately exported production env."""
import json
import os
from pathlib import Path

BASE = Path('/opt/tokenbot-website')
values = json.loads((BASE / 'environment.json').read_text())
if not isinstance(values, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in values.items()):
    raise SystemExit('Invalid website environment')
for key in ('PORTAL_DATABASE_URL', 'PORTAL_ENCRYPTION_KEY', 'QUOTA_PUBLIC_ORIGIN'):
    if not values.get(key):
        raise SystemExit('Missing required website environment')
os.environ.update(values)
os.chdir(BASE / 'current')
os.execv(str(BASE / 'venv/bin/python'), [
    str(BASE / 'venv/bin/python'), '-m', 'uvicorn', 'app.main:create_app',
    '--factory', '--host', '127.0.0.1', '--port', '8186', '--workers', '1',
    '--no-access-log', '--proxy-headers', '--forwarded-allow-ips', '127.0.0.1',
    '--limit-concurrency', '32', '--timeout-keep-alive', '5',
])
