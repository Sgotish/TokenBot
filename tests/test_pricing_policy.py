import copy
from decimal import Decimal
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tokenbot.customer_billing import BillingError
from tokenbot.pricing_policy import PriceBook, pricing_lock


@unittest.skipUnless(os.name == 'posix', 'Production pricing locks require Linux')
class PricingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'private/customers').mkdir(parents=True)
        (self.root/'private/collector.json').write_text('{"admin":{}}')
        self.cid = 'web-'+'a'*32
        (self.root/'private/customers'/(self.cid+'.json')).write_text('{"user_id":12}')
        self.registry_path = self.root/'clients.json'
        self.registry = {'clients': {self.cid: {'billing': {'status': 'active', 'multiplier': '0.5'},
            'pools': {'auto': {'group_id': 4}, 'pro': {'group_id': 5}}}}}
        self.persist()
        self.book = PriceBook(self.root, lambda: self.panel)
        self.channels = []
        self.rates = {'99': 0.7}
        self.lost = False
        self.mismatch = False
        seed = self.book.read()
        self.data = {**seed, 'reason': 'Verified public price card', 'actor': 'b'*32, 'confirmed': True}

    def tearDown(self):
        self.tmp.cleanup()

    def persist(self):
        self.registry_path.write_text(json.dumps(self.registry))

    def panel(self, method, path, token=None, body=None):
        if path == '/auth/login':
            return {'access_token': 'never-export'}
        if path.startswith('/admin/channels?'):
            return {'items': self.channels, 'total': len(self.channels)}
        if path == '/admin/channels' and method == 'POST':
            self.channels.append({**copy.deepcopy(body), 'id': 1, 'status': 'active'})
            if self.lost:
                self.lost = False
                raise BillingError('lost native response', 503)
            return self.channels[0]
        if path == '/admin/channels/1':
            if method == 'PUT':
                self.channels[0] = {**copy.deepcopy(body), 'id': 1, 'status': 'active'}
            result = copy.deepcopy(self.channels[0])
            if self.mismatch:
                result['model_pricing'][0]['input_price'] = 999
            return result
        if path == '/admin/users/12':
            if method == 'PUT':
                self.rates = copy.deepcopy(body['group_rates'])
            return {'group_rates': self.rates}
        raise AssertionError(path)

    def apply(self, **kwargs):
        return self.book.apply({**self.data, **kwargs}, self.registry_path, self.registry, self.persist)

    def test_native_per_token_and_public_per_million_apply_factor_once(self):
        result = self.apply()
        model = next(m for m in result['models'] if m['id'] == 'gpt-6.1-sol')
        native = next(m for m in self.channels[0]['model_pricing'] if m['models'] == ['gpt-6.1-sol'])
        self.assertEqual(model['prices']['input'], '1.0')
        self.assertEqual(Decimal(str(native['input_price'])), Decimal('.000002'))
        self.assertEqual(Decimal(str(native['output_price'])), Decimal('.000010'))
        # Reconcile the actual historical 17 input + 5 output probe.
        debit = (17*Decimal(str(native['input_price']))+5*Decimal(str(native['output_price'])))*Decimal(str(self.rates['4']))
        self.assertEqual(debit, Decimal('.000042'))
        self.assertEqual(self.rates['99'], .7)  # unrelated group rates preserved
        self.assertEqual(result['display_currency'], 'CNY')
        self.assertEqual(result['cny_per_credit'], '1')
        self.assertNotIn('never-export', json.dumps(result))

    def test_revision_conflict_does_not_change_prices(self):
        self.apply()
        with self.assertRaises(BillingError) as e:
            self.apply(multiplier='0.7')
        self.assertEqual(e.exception.status, 409)
        self.assertEqual(self.rates['4'], .5)
        self.assertFalse(self.registry['pricing_pending'])

    def test_lost_native_response_blocks_calls_and_retries_without_duplicate_channel(self):
        self.lost = True
        with self.assertRaises(BillingError):
            self.apply()
        self.assertTrue(self.registry['pricing_pending'])
        with self.assertRaises(BillingError):
            self.book.projection()
        with self.assertRaises(BillingError):
            with pricing_lock(self.registry_path):
                pass
        with self.assertRaises(BillingError):
            self.apply(multiplier='0.7')
        self.book = PriceBook(self.root, lambda: self.panel)
        self.assertEqual(self.apply()['version'], 1)
        self.assertEqual(len(self.channels), 1)
        self.assertFalse(self.registry['pricing_pending'])

    def test_native_readback_mismatch_never_publishes_success(self):
        self.mismatch = True
        with self.assertRaises(BillingError):
            self.apply()
        self.assertTrue(self.registry['pricing_pending'])
        self.assertEqual(self.book.read()['version'], 0)
        self.mismatch = False
        self.assertEqual(self.apply()['version'], 1)

    def test_inflight_stream_prevents_any_pricing_mutation(self):
        with pricing_lock(self.registry_path):
            with self.assertRaises(BillingError) as e:
                self.apply()
        self.assertEqual(e.exception.status, 409)
        self.assertFalse(self.channels)
        self.assertFalse(self.registry.get('pricing_pending'))

    def test_existing_shared_lock_works_on_read_only_mount(self):
        with pricing_lock(self.registry_path, exclusive=True):
            pass
        real_open = os.open
        def readonly(path, flags, *args):
            if Path(path) == self.registry_path.with_suffix('.pricing-lock') and flags & (os.O_RDWR | os.O_WRONLY | os.O_CREAT):
                raise OSError(30, 'Read-only file system')
            return real_open(path, flags, *args)
        with patch('tokenbot.pricing_policy.os.open', side_effect=readonly):
            with pricing_lock(self.registry_path):
                pass

    def test_invalid_partial_or_nonfinite_prices_never_reach_native(self):
        for change in ({'confirmed': False}, {'multiplier': 'NaN'}, {'multiplier': True},
                       {'multiplier': '0'}, {'models': []}, {'version': True}):
            with self.subTest(change=change), self.assertRaises(BillingError):
                self.apply(**change)
        invalid = copy.deepcopy(self.data['models'])
        invalid[0]['base']['input'] = '1e5'
        with self.assertRaises(BillingError):
            self.apply(models=invalid)
        self.assertFalse(self.channels)

    def test_rate_change_preserves_old_price_version(self):
        self.apply()
        updated = self.apply(version=1, multiplier='0.6')
        self.assertEqual(updated['version'], 2)
        self.assertEqual(self.rates['4'], .6)
        self.assertEqual(self.book.read()['history'][-1]['multiplier'], '0.5')


if __name__ == '__main__':
    unittest.main()
