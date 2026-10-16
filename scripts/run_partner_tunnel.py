#!/usr/bin/env python3
"""Temporary SSH HTTPS tunnel; publish only the API bridge, stop at expiry."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
runtime = ROOT / '.runtime'
os.umask(0o077)
cfg = json.loads((runtime / 'partner-test.json').read_text())
state = runtime / 'partner-tunnel.json'
state.unlink(missing_ok=True)
if time.time() >= cfg['expires_at']:
    raise SystemExit('Test key has expired.')
command = ['ssh', '-F', '/dev/null', '-o', 'IdentityAgent=none', '-o',
    'IdentitiesOnly=yes', '-o', 'IdentityFile=none', '-o', 'BatchMode=yes',
    '-o', 'StrictHostKeyChecking=accept-new', '-o',
    f'UserKnownHostsFile={runtime / "localhost-run-known-hosts"}',
    '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=30',
    '-o', 'ServerAliveCountMax=3', '-o', 'ExitOnForwardFailure=yes',
    '-T', '-R', '80:127.0.0.1:8181', 'nokey@localhost.run', '--', '--output', 'json']
child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
def stop(signum, frame):
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
selector = selectors.DefaultSelector()
selector.register(child.stdout, selectors.EVENT_READ)
pending = b''
ready = False
started = time.time()
try:
    while time.time() < cfg['expires_at'] and child.poll() is None:
        if not ready and time.time() - started > 45:
            raise RuntimeError('Tunnel did not register within 45 seconds.')
        for key, _ in selector.select(timeout=1):
            chunk = os.read(key.fileobj.fileno(), 65536)
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            pending += chunk
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                if event.get('type') != 'v1.tcpip_forward.register.accepted':
                    continue
                domain = event.get('id', '').removeprefix('localhost/')
                parsed = urlparse('https://' + domain)
                if parsed.hostname != domain or not domain.endswith('.lhr.life'):
                    raise RuntimeError('Unexpected tunnel hostname; review before sharing.')
                state.write_text(json.dumps({'base_url': 'https://' + domain + '/v1',
                    'expires_at': cfg['expires_at'], 'runner_pid': os.getpid(),
                    'ssh_pid': child.pid, 'started_at': time.time()}, indent=2))
                state.chmod(0o600)
                ready = True
                print('Temporary HTTPS endpoint registered.', flush=True)
            if len(pending) > 131072:
                pending = b''
finally:
    selector.close()
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    if state.exists():
        saved = json.loads(state.read_text())
        if saved.get('runner_pid') == os.getpid():
            saved['stopped_at'] = time.time()
            state.write_text(json.dumps(saved, indent=2))
    print('Temporary HTTPS endpoint stopped.', flush=True)
