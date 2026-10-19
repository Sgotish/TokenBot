#!/usr/bin/env python3
"""Install the isolated research services on the existing Ubuntu pilot.

No inference, balance/rate mutations or customer-service restart. Preserves
existing Caddy routes and validates the candidate before activation.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path('/opt/tokenbot-pilot')
STATE = Path('/var/lib/tokenbot-research')
UNITS = ('tokenbot-research.service', 'tokenbot-research-collect.service', 'tokenbot-research-collect.timer')


def caddy_candidate(source):
    if '/research' in source:
        if 'reverse_proxy @tokenbot_research 127.0.0.1:8185' not in source:
            raise ValueError('An existing research route requires manual reconciliation')
        return source
    pattern = re.compile(r'(?m)^([ \t]*)reverse_proxy 127\.0\.0\.1:8181[ \t]*$')
    if not pattern.search(source):
        raise ValueError('Expected pilot Caddy route not found; do not replace unrelated config')
    def insert(match):
        indent = match[1]
        return (indent+'@tokenbot_research path /research /research/*\n'+indent+
                'reverse_proxy @tokenbot_research 127.0.0.1:8185\n'+match[0])
    return pattern.sub(insert, source)


def run(*args, check=True):
    return subprocess.run(args, check=check, capture_output=True, text=True, timeout=90)


def main():
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise SystemExit('Run as root on the existing Ubuntu pilot only.')
    import grp
    from tokenbot.client import NoRedirect
    os.umask(0o077)
    config = json.loads((ROOT/'private/collector.json').read_text())
    if not config.get('accounts') or not config.get('admin'):
        raise SystemExit('Existing collector configuration is incomplete.')
    caddy = Path('/etc/caddy/Caddyfile')
    previous = caddy.read_text()
    candidate = caddy_candidate(previous)
    backup = ROOT/'backups'/('capacity-research-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(caddy, backup/'Caddyfile')
    for name in UNITS:
        live = Path('/etc/systemd/system')/name
        if live.exists():
            shutil.copy2(live, backup/name)
    gid = grp.getgrnam('tokenbot-bridge').gr_gid
    STATE.mkdir(mode=0o750, exist_ok=True)
    os.chown(STATE, 0, gid)
    os.chmod(STATE, 0o750)
    key = STATE/'access.secret'
    if not key.exists():
        key.write_text(secrets.token_urlsafe(48)+'\n')
    if len(key.read_text().strip()) < 40:
        raise SystemExit('Existing research secret is invalid; no automatic replacement.')
    os.chown(key, 0, gid)
    os.chmod(key, 0o640)
    pending = caddy.with_name('Caddyfile.research-candidate')
    pending.write_text(candidate)
    # Caddy uses its unit's hostname/IP variables; obtain only these two from
    # the running process environment, never print the environment.
    pid = run('systemctl', 'show', 'caddy', '--property=MainPID', '--value').stdout.strip()
    if not pid.isdigit() or int(pid) <= 0:
        raise SystemExit('Caddy must already be running before research installation.')
    for item in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
        name, _, value = item.partition(b'=')
        if name in (b'TOKENBOT_PUBLIC_HOST', b'TOKENBOT_PUBLIC_IP'):
            os.environ[name.decode()] = value.decode()
    run('caddy', 'validate', '--config', str(pending), '--adapter', 'caddyfile')
    for name in UNITS:
        shutil.copy2(ROOT/'deploy'/name, Path('/etc/systemd/system')/name)
        os.chmod(Path('/etc/systemd/system')/name, 0o644)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'tokenbot-research.service')
    run('systemctl', 'restart', 'tokenbot-research.service')
    # First scan must succeed before exposing the new route. Timer can be
    # started manually if upstream is temporarily down; historical data stays.
    run('systemctl', 'start', 'tokenbot-research-collect.service')
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))
    endpoint = 'http://127.0.0.1:8185/research/api/report'
    try:
        opener.open(endpoint, timeout=10)
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise
    else:
        raise RuntimeError('Unauthenticated report was not rejected')
    req = urllib.request.Request(endpoint, headers={'Authorization': 'Bearer '+key.read_text().strip()})
    with opener.open(req, timeout=10) as result:
        data = json.load(result)
    if data.get('collection_failed') or data.get('ledger_stale'):
        raise RuntimeError('Initial research scan is not healthy')
    try:
        caddy.write_text(candidate)
        run('systemctl', 'reload', 'caddy')
        run('systemctl', 'enable', '--now', 'tokenbot-research-collect.timer')
    except Exception:
        caddy.write_text(previous)
        run('systemctl', 'reload', 'caddy', check=False)
        raise
    print('Research services active. Route: /research. Access key file: '+str(key))
    print('Backup: '+str(backup))
    print('No model calls; existing inference, customer keys and prices unchanged.')


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        main()
    except Exception:
        raise SystemExit('Research installation incomplete. Review service status; private diagnostics suppressed.')
