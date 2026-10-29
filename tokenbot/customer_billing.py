"""Customer money stays in Sub2API; local state only records fulfillment metadata."""
from contextlib import contextmanager
import base64
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from .panel_session import login, invalidate


class BillingError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def amount(value, positive=False):
    try:
        number = Decimal(str(value))
        if isinstance(value, bool) or not number.is_finite():
            raise ValueError()
        if positive and (not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,2})?', value)
                         or not Decimal('0.01') <= number <= Decimal('100000')):
            raise ValueError()
        return number
    except (InvalidOperation, ValueError, TypeError):
        raise BillingError('金额无效，入账金额须为 0.01 至 100000，最多两位小数。') from None


def money(value):
    return format(amount(value), 'f')


@contextmanager
def account_lock(cfg, exclusive=False):
    """Bridge streams hold shared locks; activation requires a quiet account."""
    import fcntl
    path = Path(cfg['selection_path']).parent/'billing.lock'
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o660)
    if os.geteuid() == 0:
        os.fchown(fd, -1, path.parent.stat().st_gid)
        os.fchmod(fd, 0o660)
    with os.fdopen(fd, 'a') as handle:
        try:
            fcntl.flock(handle, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BillingError('账户正在调用或更新计费，请稍后重试。', 409) from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class Panel:
    def __init__(self):
        self.deadline = time.monotonic()+18
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def __call__(self, method, path, token=None, body=None, idempotency=None):
        remaining = self.deadline-time.monotonic()
        if remaining <= 0:
            raise BillingError('账本读取超时，请刷新核对，勿更换订单号重复入账。', 503)
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer '+token
        if idempotency:
            headers['Idempotency-Key'] = idempotency
        request = urllib.request.Request('http://127.0.0.1:8180/api/v1'+path, method=method,
            headers=headers, data=json.dumps(body).encode() if body is not None else None)
        try:
            with self.opener.open(request, timeout=min(6, remaining)) as response:
                raw = response.read(2_000_001)
            result = json.loads(raw, parse_float=Decimal)
            if len(raw)>2_000_000 or result.get('code') != 0:
                raise ValueError()
            return result['data']
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 401 and token:
                invalidate(token)
            raise BillingError('账本操作未确认，请刷新或使用相同订单号重试。', 503) from None


class CustomerBilling:
    def __init__(self, root, panel_factory=Panel):
        self.root = Path(root)
        self.private = self.root/'private'
        self.panel_factory = panel_factory

    def source(self, cid):
        source = json.loads((self.private/'customers'/(cid+'.json')).read_text())
        if type(source.get('user_id')) is not int or source['user_id'] <= 0:
            raise BillingError('客户账本身份待核对。', 503)
        return source

    def state(self, cid):
        path = self.private/'billing'/(cid+'.json')
        return json.loads(path.read_text()) if path.exists() else {'orders': {}}

    def save(self, cid, state):
        directory = self.private/'billing'
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory/(cid+'.json')
        temp = path.with_suffix('.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(state, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(path)
        if os.name == 'posix':
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def admin(self, panel):
        config = json.loads((self.private/'collector.json').read_text())
        if isinstance(panel, Panel):
            return login(panel, config['admin'])
        return panel('POST', '/auth/login', body=config['admin'])['access_token']

    def customer(self, panel, source):
        if isinstance(panel, Panel):
            return login(panel, source['partner'])
        return panel('POST', '/auth/login', body=source['partner'])['access_token']

    def stats(self, panel, token):
        # Explicit dates avoid the upstream dashboard's default period.
        end = time.strftime('%Y-%m-%d', time.gmtime())
        return panel('GET', '/usage/stats?start_date=2000-01-01&end_date='+end+'&timezone=UTC', token)

    def activate(self, cid, cfg, persist_registry, multiplier='0.3335', *, trial=None):
        multiplier = money(amount(multiplier))
        if not Decimal('0.01') <= amount(multiplier) <= Decimal('10'):
            raise BillingError('计费倍率无效。')
        if cfg.get('billing', {}).get('status') == 'active':
            return {'ok': True, 'billing_enabled': True, 'multiplier': cfg['billing']['multiplier']}
        with account_lock(cfg, exclusive=True):
            panel = self.panel_factory()
            source = self.source(cid)
            token = self.customer(panel, source)
            profile = panel('GET', '/user/profile', token)
            if profile.get('id') != source['user_id']:
                raise BillingError('客户账本身份不匹配。', 503)
            if amount(profile['balance']) not in (Decimal('0'), Decimal('1')):
                raise BillingError('现有余额不是初始测试额度，请先核对，不能自动清零。', 409)
            if cfg.get('billing', {}).get('status') != 'activating':
                stats = self.stats(panel, token)
                cfg['billing'] = {'status': 'activating', 'multiplier': multiplier,
                    'activated_at': int(time.time()), 'initial_test_balance_removed': money(profile['balance']),
                    'previous_actual_cost': money(stats['total_actual_cost']), 'currency': 'USD'}
                if trial:
                    cfg['billing'].update(mode='trial_budget', trial_limit=trial['limit'],
                                          trial_reference=trial['reference'])
                persist_registry()
            admin = self.admin(panel)
            cfg['billing']['multiplier'] = multiplier
            groups = {str(p['group_id']): float(amount(multiplier)) for p in cfg['pools'].values()}
            # Account is quiescent and bridge rejects 'activating'; retries are safe.
            panel('PUT', '/admin/users/'+str(source['user_id']), admin, {'group_rates': groups})
            updated = panel('GET', '/admin/users/'+str(source['user_id']), admin)
            if any(amount(updated.get('group_rates', {}).get(gid)) != amount(multiplier) for gid in groups):
                raise BillingError('客户倍率尚未确认，保持暂停开通，请稍后重试。', 503)
            # The upstream general user-update DTO accepts "balance" but its
            # service ignores it. Use the dedicated, audited balance endpoint.
            if amount(profile['balance']) == Decimal('1'):
                panel('POST', '/admin/users/'+str(source['user_id'])+'/balance', admin,
                    {'balance': 1, 'operation': 'subtract', 'notes': 'Remove synthetic free admission balance; no customer payment'},
                    idempotency='TB-ACTIVATE-'+cid+'-'+str(cfg['billing']['activated_at']))
            verified = panel('GET', '/user/profile', token)
            if verified.get('id') != source['user_id'] or amount(verified['balance']) != 0:
                raise BillingError('初始测试余额尚未归零，保持暂停开通，请核对后重试。', 503)
            cfg['billing']['status'] = 'active'
            persist_registry()
            return {'ok': True, 'billing_enabled': True, 'multiplier': multiplier}

    def grant_trial(self, cid, cfg, persist_registry, limit, reference, multiplier='0.3335'):
        """Trusted admin CLI only: synthetic native credits, never a payment.

        Native usage settlement and insufficient-balance checks are reused so
        all keys share one budget and concurrent calls cannot create separate
        allowances. Customer cash reservations remain untouched.
        """
        limit = format(amount(limit, True), '.2f')
        if not isinstance(reference, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{7,79}', reference):
            raise BillingError('试用额度登记编号无效。')
        existing = cfg.get('billing', {})
        if existing and (existing.get('mode') != 'trial_budget' or
                         existing.get('trial_limit') != limit or existing.get('trial_reference') != reference):
            raise BillingError('已有其他账本或试用额度，不能覆盖或重复发放。', 409)
        self.activate(cid, cfg, persist_registry, multiplier,
                      trial={'limit': limit, 'reference': reference})
        return self.credit(cid, cfg, {'reference': reference, 'credit_usd': limit,
            'paid_currency': 'CNY', 'confirmed': True, 'trial_credit': True})

    def credit(self, cid, cfg, data):
        if cfg.get('billing', {}).get('status') != 'active':
            raise BillingError('请先开通此客户的按量计费。', 409)
        reference = data.get('reference')
        if not isinstance(reference, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{7,79}', reference):
            raise BillingError('订单号须为 8 至 80 位字母、数字、点、横线或下划线。')
        if data.get('confirmed') is not True or data.get('paid_currency') not in ('CNY', 'USD', 'EUR'):
            raise BillingError('须确认实际收款，并填写收款币种。')
        credit = format(amount(data.get('credit_usd'), True), '.2f')
        testing = data.get('test_credit') is True and cfg.get('billing_qa') is True
        trial = cfg['billing'].get('mode') == 'trial_budget'
        if trial and not (data.get('trial_credit') is True and
                          reference == cfg['billing']['trial_reference'] and credit == cfg['billing']['trial_limit']):
            raise BillingError('当前为免费试用额度，不能混入实收充值或重复增加额度。', 409)
        paid = '0.00' if testing or trial else format(amount(data.get('paid_amount'), True), '.2f')
        source = self.source(cid)
        state = self.state(cid)
        order = {'reference': reference, 'credit_usd': credit, 'paid_amount': paid,
                 'paid_currency': data['paid_currency'], 'kind': 'trial_credit' if trial else 'test_credit' if testing else 'payment'}
        existing = state['orders'].get(reference)
        if existing and any(existing[k] != v for k, v in order.items()):
            raise BillingError('该订单号已登记不同金额或币种，不能重复入账。', 409)
        if existing and existing['status'] == 'credited':
            return {'ok': True, 'order': existing, 'replayed': True}
        policy = self.private/'pricing-policy.json'
        if not existing and not testing and not trial and data['paid_currency'] == 'CNY' and policy.exists():
            saved = json.loads(policy.read_text())
            if saved.get('cny_per_credit') == '1' and amount(paid) != amount(credit):
                raise BillingError('当前人民币充值为 1:1 站内额度，入账额度必须等于人民币实收金额。')
        order = existing or {**order, 'created_at': int(time.time()), 'status': 'pending',
                             'actor': data.get('actor', '')}
        state['orders'][reference] = order
        self.save(cid, state)
        panel = self.panel_factory()
        admin = self.admin(panel)
        # Fixed unique native redeem code survives HTTP idempotency TTL and restarts.
        # Native DB code is VARCHAR(32), despite its HTTP DTO allowing 128.
        code = 'TBPAY-'+base64.b32encode(hashlib.sha256(reference.encode()).digest()[:16]).decode().rstrip('=')
        result = panel('POST', '/admin/redeem-codes/create-and-redeem', admin,
            {'code': code, 'type': 'balance', 'value': float(credit), 'user_id': source['user_id'],
             'notes': ('TokenBots FREE TRIAL NO PAYMENT ' if trial else 'TokenBots QA credit NO PAYMENT ' if testing else 'TokenBots manual payment ')+reference}, idempotency=code)['redeem_code']
        if (result.get('used_by') != source['user_id'] or amount(result.get('value')) != amount(credit)
                or result.get('status') != 'used'):
            raise BillingError('原生充值记录与订单不符，已暂停确认，请管理员核对。', 409)
        order.update(status='credited', credited_at=int(time.time()), ledger_id=result['id'])
        self.save(cid, state)
        return {'ok': True, 'order': order, 'replayed': bool(existing)}

    def view(self, cid, cfg, page=1):
        if type(page) is not int or not 1 <= page <= 10000:
            raise BillingError('账单页码无效。')
        billing = cfg.get('billing', {})
        trial = billing.get('mode') == 'trial_budget'
        if billing.get('status') != 'active':
            return {'billing_enabled': False, 'status': billing.get('status', 'free_test'),
                    'currency': 'USD', 'multiplier': billing.get('multiplier', '0.3335'), 'items': [], 'orders': []}
        source = self.source(cid)
        panel = self.panel_factory()
        token = self.customer(panel, source)
        profile = panel('GET', '/user/profile', token)
        if profile.get('id') != source['user_id']:
            raise BillingError('客户账本身份不匹配。', 503)
        stats = self.stats(panel, token)
        records = panel('GET', '/usage?'+urllib.parse.urlencode({'page': page, 'page_size': 20,
            'sort_by': 'created_at', 'sort_order': 'desc'}), token)
        items = []
        for row in records['items']:
            # Strict allowlist: no upstream accounts, keys, IPs or customer content.
            fields = ('id', 'created_at', 'model', 'input_tokens', 'output_tokens',
                      'cache_read_tokens', 'cache_creation_tokens')
            item = {k: row.get(k) for k in fields}
            complete = all(type(row.get(k)) is int and row[k] >= 0 for k in fields[3:])
            item.update(amount_usd=money(row['actual_cost']) if row.get('actual_cost') is not None else None,
                        multiplier=money(row['rate_multiplier']) if row.get('rate_multiplier') is not None else None,
                        status='settled' if complete and row.get('actual_cost') is not None else 'needs_review')
            if item['multiplier'] == '0':
                item['status'] = 'free_test'
            elif trial and item['status'] == 'settled':
                item['status'] = 'trial_usage'
            items.append(item)
        orders = list(self.state(cid)['orders'].values())
        public_orders = [{k: o.get(k) for k in ('reference', 'credit_usd', 'paid_amount',
            'paid_currency', 'created_at', 'credited_at', 'status', 'kind')} for o in orders]
        spent = amount(stats['total_actual_cost'])-amount(billing['previous_actual_cost'])
        return {'billing_enabled': not trial, 'metering_enabled': True, 'trial_budget': trial,
            'cash_debited': '0' if trial else None,
            'status': 'trial_budget' if trial else 'active', 'currency': 'CNY' if trial else 'USD', 'multiplier': billing['multiplier'],
            'generated_at': time.time(), 'activated_at': billing['activated_at'],
            'balance_usd': money(profile['balance']), 'spent_usd': money(spent),
            'credited_usd': money(sum((amount(o['credit_usd']) for o in orders if o['status']=='credited'), Decimal(0))),
            'items': items, 'page': records['page'], 'pages': records['pages'], 'total': records['total'],
            'orders': sorted(public_orders, key=lambda o: o['created_at'], reverse=True)}
