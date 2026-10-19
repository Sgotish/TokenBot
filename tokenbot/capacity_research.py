"""Passive subscription capacity research. Never changes customer billing.

Sub2API counters are disjoint: its input_tokens already excludes cached tokens.
The historical quota view is rounded; rates below are observational estimates,
not an upstream entitlement or a causal per-token tariff.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import sqlite3

from .usage_snapshot import epoch

TOKENS = ('input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_creation_tokens')
WINDOWS = {'5 小时窗口': 18000, '7 天窗口': 604800}
GUARD = 120  # Conservative allowance for delayed quota/log accounting.
MIN_POINTS = 5
MIN_SECONDS = 1800
MAX_GAP = 900


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript('''
      CREATE TABLE IF NOT EXISTS usage (
        id INTEGER PRIMARY KEY, account TEXT NOT NULL, stamp REAL NOT NULL,
        payload TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS usage_account_time ON usage(account, stamp);
      CREATE TABLE IF NOT EXISTS quota (
        account TEXT NOT NULL, seconds INTEGER NOT NULL, stamp REAL NOT NULL,
        reset REAL NOT NULL, used REAL NOT NULL,
        PRIMARY KEY(account, seconds, stamp));
      CREATE TABLE IF NOT EXISTS scans (
        start REAL NOT NULL, end REAL NOT NULL, collected REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')
    return db


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def usage_row(raw):
    """Retain no credentials, customer content, IPs, email or nested DTOs."""
    if type(raw.get('id')) is not int or raw['id'] <= 0:
        raise ValueError('Missing stable usage ID')
    account = raw.get('account_id') or (raw.get('account') or {}).get('id')
    stamp = epoch(raw.get('created_at'))
    if type(account) is not int or account <= 0 or stamp is None:
        raise ValueError('Missing usage identity/time')
    counts = {key: raw.get(key) for key in TOKENS}
    valid = all(type(v) is int and v >= 0 for v in counts.values())
    duration = raw.get('duration_ms')
    if not finite(duration) or duration < 0:
        valid = False
        duration = None
    model = raw.get('upstream_model') or raw.get('model')
    if not isinstance(model, str) or not model or len(model) > 200:
        model, valid = 'unknown', False
    # Generated media and failed/ambiguous records must not calibrate text rates.
    if any(raw.get(k) for k in ('image_count', 'video_count', 'image_input_tokens', 'image_output_tokens')):
        valid = False
    if raw.get('billing_mode') not in (None, '', 'token', 'tokens'):
        valid = False
    if raw.get('request_type') == 'cyber' or raw.get('upstream_model_mismatch'):
        valid = False
    def field(*names):
        for name in names:
            v = raw.get(name)
            if isinstance(v, str) and 0 < len(v) <= 100:
                return v
        return 'unknown'
    user_id = raw.get('user_id')
    return {'id': raw['id'], 'account': str(account), 'stamp': stamp,
            'user_id': user_id if type(user_id) is int and user_id > 0 else None,
            'model': model, 'effort': field('upstream_reasoning_effort', 'reasoning_effort'),
            'tier': field('service_tier'), 'duration_ms': duration,
            'valid': valid, **counts}


def save_scan(db, rows, start, end, collected):
    with db:
        db.executemany('INSERT OR REPLACE INTO usage VALUES (?,?,?,?)',
                       [(r['id'], r['account'], r['stamp'], json.dumps(r)) for r in rows])
        db.execute('INSERT INTO scans VALUES (?,?,?)', (start, end, collected))


def save_quota(db, snapshot, accounts, now):
    """Reuse the existing refresh timer: this module never calls quota refresh."""
    labels = Counter(accounts.values())
    mapping = {v: str(k) for k, v in accounts.items() if labels[v] == 1}
    with db:
        for a in snapshot.get('accounts', []):
            stamp = epoch(a.get('snapshot_at'))
            if a.get('label') not in mapping or a.get('source') != 'quota_api' or a.get('snapshot_stale'):
                continue
            if stamp is None or stamp > now + 5 or now - stamp > 180:
                continue
            for w in a.get('windows', []):
                seconds, reset = WINDOWS.get(w.get('label')), epoch(w.get('resets_at'))
                remaining = w.get('remaining_percent')
                if not seconds or w.get('stale') or reset is None or reset <= stamp:
                    continue
                if not finite(remaining) or not 0 <= remaining <= 100:
                    continue
                db.execute('INSERT OR IGNORE INTO quota VALUES (?,?,?,?,?)',
                           (mapping[a['label']], seconds, stamp, reset, 100 - remaining))


def total(row):
    return sum(v for k in TOKENS if type(v := row.get(k)) is int and v >= 0)


def covered(scans, start, end, settled_at=None):
    cursor = start
    for s in sorted(scans, key=lambda s: s['start']):
        if settled_at is not None and s['collected'] < settled_at:
            continue
        if s['end'] < cursor:
            continue
        if s['start'] > cursor:
            return False
        cursor = max(cursor, s['end'])
        if cursor >= end:
            return True
    return False


def measure(quota, rows, scans, now):
    blocks, rejected = [], Counter()
    anchor = previous = None
    for q in quota:
        if q['stamp'] > now - GUARD:
            break
        if anchor is None:
            anchor = previous = q
            continue
        reason = None
        if abs(q['reset'] - previous['reset']) > 120 or q['stamp'] >= anchor['reset']:
            reason = 'reset'
        elif q['stamp'] - previous['stamp'] > MAX_GAP:
            reason = 'snapshot_gap'
        elif q['used'] < previous['used'] - 0.01:
            reason = 'quota_decreased'
        previous = q
        if reason:
            rejected[reason] += 1
            anchor = q
            continue
        delta = q['used'] - anchor['used']
        if delta < MIN_POINTS or q['stamp'] - anchor['stamp'] < MIN_SECONDS:
            continue
        start, end = anchor['stamp'], q['stamp']
        anchor = q
        if not covered(scans, start - GUARD, end + GUARD, end + GUARD):
            rejected['ledger_gap'] += 1
            continue
        inside = [r for r in rows if start < r['stamp'] <= end]
        # Include duration on BOTH sides: upstream created_at semantics differ by
        # version. This deliberately overestimates ambiguous boundary tokens.
        nearby = [r for r in rows if start - GUARD - (r['duration_ms'] or 0)/1000 <= r['stamp']
                  <= end + GUARD + (r['duration_ms'] or 0)/1000]
        if any(not r['valid'] for r in nearby):
            rejected['invalid_usage'] += 1
            continue
        tokens = sum(total(r) for r in inside)
        if not tokens:
            rejected['quota_without_tokens'] += 1
            continue
        boundary = sum(total(r) for r in nearby if min(abs(r['stamp']-start), abs(r['stamp']-end))
                       <= GUARD + (r['duration_ms'] or 0)/1000)
        if boundary > tokens * .25:
            rejected['boundary_uncertainty'] += 1
            continue
        cohorts = {(r['model'], r['effort'], r['tier']) for r in nearby if total(r)}
        blocks.append({'start': start, 'end': end, 'points': delta, 'tokens': tokens,
                       'boundary_tokens': boundary, 'requests': len(inside),
                       'cohort': list(next(iter(cohorts))) if len(cohorts) == 1 else None,
                       'composition': {k: sum(r[k] for r in inside) for k in TOKENS}})
    return blocks, dict(rejected)


def estimate(blocks, seconds, cohort=None):
    points = sum(b['points'] for b in blocks)
    tokens = sum(b['tokens'] for b in blocks)
    boundary = sum(b['boundary_tokens'] for b in blocks)
    rate = points * 1e6 / tokens
    # At least 1 percentage point endpoint-difference uncertainty per block;
    # not a statistical confidence interval and does not include unlogged use.
    low = max(0, points - len(blocks)) * 1e6 / (tokens + boundary)
    high = (points + len(blocks)) * 1e6 / (tokens - boundary)
    capacities = [b['tokens'] / b['points'] * 100 for b in blocks]
    composition = {k: sum(b['composition'][k] for b in blocks) for k in TOKENS}
    return {'cohort': cohort, 'window_seconds': seconds, 'blocks': len(blocks),
            'status': 'observed' if len(blocks) >= 3 and points >= 15 else 'provisional',
            'points': points, 'tokens': tokens, 'requests': sum(b['requests'] for b in blocks),
            'points_per_million': rate, 'rate_sensitivity': [low, high],
            'window_capacity_tokens': 100e6 / rate,
            'capacity_sample_range': [min(capacities), max(capacities)],
            'monthly_capacity_tokens': 100e6 / rate * 30/7 if seconds == 604800 else None,
            'composition': composition, 'first_sample': min(b['start'] for b in blocks),
            'last_sample': max(b['end'] for b in blocks)}


def pricing(monthly_tokens, account_cost, overhead, utilization, fee, margin):
    """Scenario only; callers must not apply this to balances or rate tables."""
    values = (monthly_tokens, account_cost, overhead, utilization, fee, margin)
    if not all(finite(v) for v in values) or monthly_tokens <= 0 or account_cost < 0 or overhead < 0:
        raise ValueError('Invalid pricing inputs')
    if not 0 < utilization <= 1 or not 0 <= fee < 1 or not 0 <= margin < 1 or fee+margin >= 1:
        raise ValueError('Invalid pricing ratios')
    cost_per_m = (account_cost + overhead) / (monthly_tokens * utilization / 1e6)
    return {'break_even_per_million': cost_per_m/(1-fee),
            'target_per_million': cost_per_m/(1-fee-margin),
            'sold_tokens_per_month': monthly_tokens*utilization}


def usage_visual(rows, scans, now, identity_complete=True):
    """Aggregate only the supplied scope. Never include individual identities."""
    periods = []
    for name, span, count in [('5h', 18000, 30), ('7d', 604800, 28), ('30d', 2592000, 30)]:
        start, step = now-span, span/count
        buckets = [{'stamp': start+i*step, 'tokens': 0, 'requests': 0} for i in range(count)]
        models = defaultdict(lambda: {'tokens': 0, 'requests': 0})
        composition = dict.fromkeys(TOKENS, 0)
        invalid = 0
        for row in rows:
            if not start < row['stamp'] <= now:
                continue
            tokens = total(row)
            bucket = buckets[min(count-1, int((row['stamp']-start)/step))]
            bucket['tokens'] += tokens
            bucket['requests'] += 1
            models[row['model']]['tokens'] += tokens
            models[row['model']]['requests'] += 1
            invalid += not row['valid']
            for key in TOKENS:
                if type(row.get(key)) is int and row[key] >= 0:
                    composition[key] += row[key]
        for bucket in buckets:
            bucket['complete'] = identity_complete and bucket['stamp'] < now-GUARD and covered(
                scans, bucket['stamp'], min(bucket['stamp']+step, now-GUARD))
        periods.append({'period': name, 'from': start, 'to': now, 'buckets': buckets,
            'tokens': sum(b['tokens'] for b in buckets), 'requests': sum(b['requests'] for b in buckets),
            'models': dict(sorted(models.items())), 'composition': composition,
            'invalid_records': invalid, 'complete': identity_complete and covered(scans, start, now-GUARD)})
    last = max((s['collected'] for s in scans), default=None)
    return {'generated_at': now, 'last_complete_scan': last,
            'stale': last is None or now-last > 900, 'periods': periods, 'billing_enabled': False}


def customer_visual(db, user_id, now):
    if type(user_id) is not int or user_id <= 0:
        raise ValueError('Invalid customer identity')
    all_rows = [json.loads(r[0]) for r in db.execute('SELECT payload FROM usage WHERE stamp > ?', (now-2592000,))]
    return usage_visual([r for r in all_rows if r.get('user_id') == user_id],
                        list(db.execute('SELECT * FROM scans')), now,
                        identity_complete=all(r.get('user_id') is not None for r in all_rows))


def report(db, accounts, now):
    scans = list(db.execute('SELECT * FROM scans'))
    items = []
    for aid, label in accounts.items():
        rows = [json.loads(r[0]) for r in db.execute('SELECT payload FROM usage WHERE account=? ORDER BY stamp', (str(aid),))]
        windows = []
        for seconds in WINDOWS.values():
            q = list(db.execute('SELECT * FROM quota WHERE account=? AND seconds=? ORDER BY stamp', (str(aid), seconds)))
            blocks, rejected = measure(q, rows, scans, now)
            estimates = []
            if blocks:
                estimates.append(estimate(blocks, seconds))
                groups = defaultdict(list)
                for b in blocks:
                    if b['cohort']:
                        groups[tuple(b['cohort'])].append(b)
                estimates.extend(estimate(v, seconds, list(k)) for k, v in sorted(groups.items()))
            history = [dict(point) for point in q if point['stamp'] >= now-86400]
            for point in history:
                point.pop('account', None)
                point.pop('seconds', None)
            windows.append({'seconds': seconds, 'snapshots': len(q), 'last_snapshot': dict(q[-1]) if q else None,
                            'history': history,
                            'estimates': estimates, 'excluded': rejected})
        actual = []
        for name, span in [('5h', 18000), ('7d', 604800), ('30d', 2592000)]:
            selected = [r for r in rows if now-span < r['stamp'] <= now]
            by_model = defaultdict(lambda: {'requests': 0, 'tokens': 0, 'invalid_records': 0, **dict.fromkeys(TOKENS, 0)})
            for r in selected:
                m = by_model[r['model']]
                m['requests'] += 1
                m['tokens'] += total(r)
                m['invalid_records'] += not r['valid']
                for k in TOKENS:
                    if type(r[k]) is int and r[k] >= 0:
                        m[k] += r[k]
            actual.append({'period': name, 'complete': covered(scans, now-span, now-GUARD),
                           'models': dict(sorted(by_model.items()))})
        items.append({'account': str(aid), 'label': label, 'actual': actual, 'windows': windows,
                      'visualization': usage_visual(rows, scans, now)})
    last = max((s['collected'] for s in scans), default=None)
    return {'version': 1, 'generated_at': now, 'last_complete_scan': last,
            'ledger_stale': last is None or now-last > 900,
            'history_start': min((s['start'] for s in scans), default=None),
            'accounts': items, 'measurement': {'minimum_points': MIN_POINTS, 'minimum_seconds': MIN_SECONDS,
            'boundary_guard_seconds': GUARD, 'quota_error_points_per_block': 1},
            'limitations': ['只统计上游日志已记录的用量；平台外使用、失败重试和日志缺失无法自动排除。',
                           '每个模型价格只适用于已观察到的输入、输出、缓存、推理强度和速度组合。',
                           '30 天容量按周容量乘 30/7 推算；不是月套餐承诺，短窗口或速率限制可能进一步约束容量。',
                           '账号成本只计算一次；不同模型的完整容量共享同一套餐，不能相加。',
                           '敏感区间只反映百分比取整和边界请求，不是统计置信区间。']}


def prune(db, now):
    with db:
        for table, col in [('usage', 'stamp'), ('quota', 'stamp'), ('scans', 'end')]:
            db.execute('DELETE FROM '+table+' WHERE '+col+' < ?', (now - 90*86400,))
