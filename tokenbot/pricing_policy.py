"""Versioned price book; Sub2API remains the only monetary ledger.

Amounts in this file are per million tokens. Native channel prices are per token.
The bridge holds a shared pricing lock through streaming; updates take it exclusively.
A durable pending marker blocks inference after any unconfirmed native operation.
"""
from contextlib import contextmanager
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import time

from .customer_billing import BillingError, CustomerBilling, Panel, amount, money
from .model_catalog import MODEL_EFFORTS

FIELDS = ('input', 'output', 'cache_read', 'cache_write')
NATIVE = dict(zip(FIELDS, ('input_price', 'output_price', 'cache_read_price', 'cache_write_price')))
BASE = {
    'gpt-6.1-sol': ('2', '10', '.1', '2.5'),
    'gpt-6-astra': ('10', '50', '1', '12.5'),
    'gpt-6-sol': ('2', '10', '.2', '2.5'),
    'gpt-6-luna': ('.1', '.5', '.01', '.125'),
    'gpt-5.6-sol': ('4', '20', '.4', '5'),
    'gpt-5.6-terra': ('2', '12', '.2', '2.5'),
    'gpt-5.6-luna': ('.2', '1.2', '.02', '.25'),
}
CHANNEL = 'TokenBot website pricing'


@contextmanager
def pricing_lock(registry_path, exclusive=False):
    import fcntl
    path = Path(registry_path).with_suffix('.pricing-lock')
    # Inference runs in a read-only systemd mount namespace. flock(LOCK_SH)
    # needs only a read descriptor; opening a pre-created lock for writing
    # makes every request fail with EROFS after a pricing update.
    try:
        fd = os.open(path, os.O_RDWR if exclusive else os.O_RDONLY)
    except FileNotFoundError:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o660)
    if os.geteuid() == 0:
        os.fchown(fd, -1, Path(registry_path).stat().st_gid)
        os.fchmod(fd, 0o660)
    with os.fdopen(fd, 'r+' if exclusive else 'r') as handle:
        try:
            fcntl.flock(handle, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BillingError('当前有调用或价格同步正在进行，请稍后重试。', 409) from None
        try:
            if not exclusive and json.loads(Path(registry_path).read_text()).get('pricing_pending'):
                raise BillingError('价格正在同步，暂时暂停新调用，请稍后重试。', 503)
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def decimal_setting(value, low, high):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,5}(?:\.[0-9]{1,6})?', value):
        raise BillingError('价格必须是有效十进制数，最多六位小数。')
    number = amount(value)
    if not Decimal(low) <= number <= Decimal(high):
        raise BillingError('价格或倍率超出允许范围。')
    return money(number.normalize())


class PriceBook:
    def __init__(self, root, panel_factory=Panel):
        self.root = Path(root)
        self.path = self.root/'private/pricing-policy.json'
        self.panel_factory = panel_factory
        self.billing = CustomerBilling(root, panel_factory)

    def read(self):
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {'version': 0, 'updated_at': 0, 'multiplier': '0.5',
                'models': [{'id': mid, 'base': dict(zip(FIELDS, map(money, values)))} for mid, values in BASE.items()]}

    def write(self, document):
        temp = self.path.with_suffix('.tmp')
        fd = os.open(temp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(document, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(self.path)
        if os.name == 'posix':
            fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def projection(self, admin=False):
        saved = self.read()
        pending = saved.get('pending')
        if not admin and (not saved['version'] or pending):
            raise BillingError('价格正在核对，请稍后刷新。', 503)
        active = pending or saved
        result = {k: active[k] for k in ('multiplier',)}
        result.update(version=saved['version'], updated_at=saved['updated_at'], currency='USD',
                      display_currency='CNY', cny_per_credit='1',
                      context_note='当前各上下文统一单价', service_tiers=['standard'],
                      source='https://developers.openai.com/api/docs/pricing',
                      source_checked_at='2026-10-23', models=[])
        for row in active['models']:
            result['models'].append({'id': row['id'], 'provider': 'OpenAI', 'family': 'GPT',
                'base': row['base'], 'prices': {k: money(amount(v)*amount(active['multiplier'])) for k, v in row['base'].items()}})
        if admin:
            result.update(pending=bool(pending), initialized=bool(saved['version']),
                          reason=active.get('reason', ''), audit=saved.get('history', [])[-10:])
        return result

    @staticmethod
    def validate(data):
        if data.get('confirmed') is not True:
            raise BillingError('请确认将价格同步到实际计费。')
        reason = data.get('reason')
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 200:
            raise BillingError('请填写调价说明，最多 200 字。')
        if type(data.get('version')) is not int or data['version'] < 0:
            raise BillingError('价格版本无效。')
        factor = decimal_setting(data.get('multiplier'), '0.01', '10')
        models = data.get('models')
        if not isinstance(models, list) or len(models) != len(MODEL_EFFORTS):
            raise BillingError('请提交全部已开放模型的价格。')
        result = []
        ids = set()
        for row in models:
            if not isinstance(row, dict) or row.get('id') not in MODEL_EFFORTS or row['id'] in ids:
                raise BillingError('模型价格有重复或未知模型。')
            ids.add(row['id'])
            base = row.get('base')
            if not isinstance(base, dict) or set(base) != set(FIELDS):
                raise BillingError('模型价格字段不完整。')
            result.append({'id': row['id'], 'base': {k: decimal_setting(base[k], '0.000001', '10000') for k in FIELDS}})
        result.sort(key=lambda x: list(MODEL_EFFORTS).index(x['id']))
        return {'multiplier': factor, 'models': result, 'reason': reason.strip(), 'actor': data.get('actor', '')}

    @staticmethod
    def channel_payload(policy, group_ids):
        rows = []
        for row in policy['models']:
            rates = {NATIVE[k]: float(amount(v)/Decimal(1000000)) for k, v in row['base'].items()}
            # One explicit interval prevents fallback long-context surcharges.
            # Fast/Flex are unavailable at the public bridge.
            rows.append({'platform': 'openai', 'models': [row['id']], 'billing_mode': 'token',
                         **rates, 'intervals': [{'min_tokens': 0, 'max_tokens': None,
                                                'tier_label': 'standard', **rates}]})
        return {'name': CHANNEL, 'description': 'TokenBot managed standard token prices; USD units per token',
                'group_ids': sorted(group_ids), 'billing_model_source': 'requested',
                'restrict_models': False, 'model_pricing': rows}

    @staticmethod
    def verify_channel(actual, desired):
        if (set(actual.get('group_ids', [])) != set(desired['group_ids']) or
                actual.get('billing_model_source') != 'requested' or actual.get('status') != 'active'):
            raise BillingError('模型价格绑定尚未确认，请保持参数不变并重试。', 503)
        got = {tuple(row['models']): row for row in actual.get('model_pricing', [])}
        if len(got) != len(desired['model_pricing']):
            raise BillingError('模型价格数量未确认。', 503)
        for expected in desired['model_pricing']:
            row = got.get(tuple(expected['models']), {})
            for key in NATIVE.values():
                if amount(row.get(key)) != amount(expected[key]):
                    raise BillingError('模型单价读回不一致，暂停新调用等待重试。', 503)
            intervals = row.get('intervals', [])
            if len(intervals) != 1 or intervals[0].get('min_tokens') != 0 or intervals[0].get('max_tokens') is not None:
                raise BillingError('上下文价格规则未确认。', 503)
            if any(amount(intervals[0].get(k)) != amount(expected[k]) for k in NATIVE.values()):
                raise BillingError('上下文单价读回不一致。', 503)

    def apply(self, data, registry_path, registry, persist_registry):
        desired = self.validate(data)
        saved = self.read()
        if data['version'] != saved['version']:
            raise BillingError('价格已被其他操作更新，请重新读取。', 409)
        if saved.get('pending') and any(saved['pending'][k] != desired[k] for k in ('multiplier', 'models')):
            raise BillingError('上次价格同步尚未完成，请先使用原参数重试。', 409)
        clients = {cid: cfg for cid, cfg in registry['clients'].items() if cid.startswith('web-')}
        groups = {p['group_id'] for cfg in clients.values() for p in cfg['pools'].values()}
        if not groups:
            raise BillingError('尚无模型接入分组，请先开通接入。', 409)
        with pricing_lock(registry_path, exclusive=True):
            # Registry marker is written first so a crash cannot permit mixed prices.
            registry['pricing_pending'] = True
            persist_registry()
            desired = saved.get('pending') or desired
            saved['pending'] = desired
            self.write(saved)
            panel = self.panel_factory()
            admin = self.billing.admin(panel)
            channels = panel('GET', '/admin/channels?page=1&page_size=100', admin)
            existing = [c for c in channels['items'] if c['name'] == CHANNEL]
            if len(existing) > 1 or channels.get('total', 0) > 100:
                raise BillingError('价格渠道需要管理员核对。', 409)
            payload = self.channel_payload(desired, groups)
            if existing:
                channel_id = existing[0]['id']
                panel('PUT', '/admin/channels/'+str(channel_id), admin, {**payload, 'status': 'active'})
            else:
                channel_id = panel('POST', '/admin/channels', admin, payload)['id']
            actual = panel('GET', '/admin/channels/'+str(channel_id), admin)
            self.verify_channel(actual, payload)
            for cid, cfg in clients.items():
                if cfg.get('billing', {}).get('status') != 'active':
                    continue
                source = self.billing.source(cid)
                target = '/admin/users/'+str(source['user_id'])
                current = panel('GET', target, admin)
                rates = {k: float(amount(v)) for k, v in (current.get('group_rates') or {}).items()}
                requested = {str(p['group_id']): float(amount(desired['multiplier'])) for p in cfg['pools'].values()}
                rates.update(requested)
                panel('PUT', target, admin, {'group_rates': rates})
                readback = panel('GET', target, admin)
                if any(amount(readback.get('group_rates', {}).get(gid)) != amount(desired['multiplier']) for gid in requested):
                    raise BillingError('客户倍率读回不一致，暂停新调用等待重试。', 503)
                cfg['billing']['multiplier'] = desired['multiplier']
            version = saved['version']+1
            now = int(time.time())
            history = saved.get('history', []) + [{k: saved[k] for k in ('version', 'updated_at', 'multiplier', 'models')}]
            self.write({**desired, 'version': version, 'updated_at': now, 'channel_id': channel_id,
                        'cny_per_credit': '1', 'history': history})
            registry.update(pricing_pending=False, pricing_version=version, billing_live=True,
                            pricing_multiplier=desired['multiplier'])
            persist_registry()
            return self.projection(admin=True)
