"""Reuse private panel access tokens instead of creating refresh sessions every poll.

No passwords or refresh tokens are persisted here. All reads still go to the
panel with the customer's own bearer token; this is not a cache of balances.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time


DEFAULT_DIRECTORY = Path('/var/lib/tokenbot-auth')


def login(panel, credentials, directory=DEFAULT_DIRECTORY, now=None):
    now = time.time() if now is None else now
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    # A password rotation selects a new entry. Neither identity nor password is
    # present in the filename; cache files and lock files remain owner-only.
    ident = hashlib.sha256(json.dumps(credentials, sort_keys=True).encode()).hexdigest()
    path = directory/(ident+'.json')
    fd = os.open(directory/(ident+'.lock'), os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            cached = json.loads(path.read_text())
        except (OSError, ValueError):
            cached = {}
        if cached.get('expires_at', 0) > now and cached.get('access_token'):
            return cached['access_token']
        result = panel('POST', '/auth/login', body=credentials)
        token = result['access_token']
        # Stop reuse before upstream expiry; missing expiry means no cache.
        ttl = max(0, min(900, int(result.get('expires_in', 0))-60))
        temp = path.with_suffix('.tmp')
        fd = os.open(temp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump({'access_token': token, 'expires_at': now+ttl}, handle)
        temp.replace(path)
        return token


def invalidate(token, directory=DEFAULT_DIRECTORY):
    """Invalidate a rejected access token without retrying monetary writes."""
    for path in Path(directory).glob('*.json'):
        try:
            if json.loads(path.read_text()).get('access_token') == token:
                # Use the same lock to avoid deleting a newer login result.
                with path.with_suffix('.lock').open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    if json.loads(path.read_text()).get('access_token') == token:
                        path.unlink()
        except (FileNotFoundError, ValueError):
            continue
