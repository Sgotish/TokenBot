"""Bounded per-customer failure metadata; never store credentials or prompt bodies."""
import fcntl
import json
import logging
import os
from pathlib import Path
import secrets
import time

LIMIT = 100
MAX_BYTES = 100_000


def recent_failures(cfg):
    if not cfg.get('selection_path'):
        return []
    path = Path(cfg['selection_path']).parent/'gateway-failures.json'
    try:
        with path.open('rb') as f:
            raw = f.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES:
            raise ValueError('oversize')
        rows = json.loads(raw)
        if not isinstance(rows, list):
            raise ValueError('invalid')
        return rows[:LIMIT]
    except FileNotFoundError:
        return []


def record_failure(cfg, model, status, code, elapsed, not_forwarded=True):
    event = {'request_id': secrets.token_hex(8), 'created_at': time.time(),
             'model': model, 'status_code': status, 'error_code': code,
             'duration_ms': round(elapsed*1000), 'not_forwarded': not_forwarded}
    try:
        parent = Path(cfg['selection_path']).parent
        with (parent/'gateway-failures.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                rows = recent_failures(cfg)
            except (OSError, ValueError):
                rows = []
            path = parent/'gateway-failures.json'
            temp = path.with_suffix('.tmp')
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                json.dump([event, *rows][:LIMIT], f)
                f.flush(); os.fsync(f.fileno())
            temp.replace(path)
    except (OSError, ValueError, KeyError) as exc:
        logging.getLogger(__name__).error('gateway_failure_record_unavailable type=%s errno=%s', type(exc).__name__, getattr(exc, 'errno', None))
    return event['request_id']
