"""Allowlisted views of upstream quota snapshots and partner request records."""
from datetime import datetime, timezone
import math


def epoch(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except (ValueError, TypeError, AttributeError):
        return None


def account_view(account, label, now):
    extra = account.get('extra') or {}
    stamp = extra.get('codex_usage_updated_at')
    observed = epoch(stamp)
    old = observed is None or now-observed > 900
    windows = []
    for code, title in [('5h', '5 小时窗口'), ('7d', '7 天窗口')]:
        prefix = 'codex_'+code
        value = extra.get(prefix+'_used_percent')
        reset = extra.get(prefix+'_reset_at')
        deadline = epoch(reset)
        duration = extra.get(prefix+'_window_minutes')
        reason = None
        if not isinstance(duration, (int,float)) or duration <= 0 or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value < 0:
            reason = '上游未提供此窗口，不能推算剩余量'
        elif deadline is None:
            reason = '上游未提供重置时间，剩余量待核对'
        elif deadline <= now:
            reason = '旧窗口已结束，等待上游新快照'
        remaining = None if reason else round(max(0, min(100, 100-value)), 1)
        windows.append({'label': title, 'remaining_percent': remaining, 'resets_at': reset,
                        'stale': old or bool(reason), 'reason': reason or ('历史快照，非实时余额；重置：'+str(reset) if old else None)})
    return {'label': label, 'status': account.get('status'), 'schedulable': account.get('schedulable') is True,
            'snapshot_at': stamp, 'snapshot_stale': old, 'windows': windows}


def record_view(record, accounts, groups):
    return {'created_at': record.get('created_at'), 'pool': groups.get(str(record.get('group_id')), '历史分组'),
            'account': accounts.get(str(record.get('account_id')), '未知账号'),
            'model': record.get('model'), 'duration_ms': record.get('duration_ms'),
            'total_tokens': sum(int(record.get(k) or 0) for k in ('input_tokens','output_tokens','cache_read_tokens','cache_creation_tokens')),
            **{k:int(record.get(k) or 0) for k in ('input_tokens','output_tokens','cache_read_tokens','cache_creation_tokens')}}


def quota_view(account, label, quota, now):
    """Project a fresh /wham/usage result; never export identity or credit data."""
    fetched = quota.get('fetched_at')
    if isinstance(fetched, bool) or not isinstance(fetched, (int, float)) or not math.isfinite(fetched) or fetched > now + 60 or now-fetched > 180:
        raise ValueError('Quota response has no fresh timestamp')
    limit = quota.get('rate_limit')
    if not isinstance(limit, dict):
        raise ValueError('Quota response has no rate limit data')
    extra = {'codex_usage_updated_at': datetime.fromtimestamp(fetched, timezone.utc).isoformat()}
    for name in ('primary_window', 'secondary_window'):
        window = limit.get(name)
        if not isinstance(window, dict):
            continue
        duration = window.get('limit_window_seconds')
        code = {18000: '5h', 604800: '7d'}.get(duration) if isinstance(duration, (int, float)) else None
        if not code:
            continue
        prefix = 'codex_'+code
        reset = window.get('reset_at')
        if isinstance(reset, bool) or not isinstance(reset, (int, float)) or not math.isfinite(reset):
            reset = None
        extra.update({prefix+'_used_percent': window.get('used_percent'),
                      prefix+'_window_minutes': duration/60,
                      prefix+'_reset_at': datetime.fromtimestamp(reset, timezone.utc).isoformat() if reset else None})
    view = account_view({**account, 'extra': extra}, label, now)
    view.update(source='quota_api', refresh_error=None, last_attempt_at=now)
    return view
