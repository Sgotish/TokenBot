from contextlib import nullcontext
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tokenbot.customer_billing import BillingError, CustomerBilling, account_lock, amount


class BillingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.private = self.root/'private'
        (self.private/'customers').mkdir(parents=True)
        self.cid = 'web-'+'a'*32
        (self.private/'customers'/(self.cid+'.json')).write_text(json.dumps(
            {'user_id': 12, 'partner': {'email': 'synthetic', 'password': 'never-export'}}))
        (self.private/'collector.json').write_text('{"admin":{"email":"admin-fixture"}}')
        self.cfg = {'selection_path': str(self.root/'selection.json'), 'pools': {'pro': {'group_id':5}, 'plus': {'group_id':4}}}
        self.balance = Decimal('1')
        self.cost = Decimal('0')
        self.rates = {'5': 0, '4': 0}
        self.codes = {}
        self.calls = []
        self.lose_response = False
        self.billing = CustomerBilling(self.root, lambda: self.panel)
        self.credit = {'reference':'payment-20261023-001','credit_usd':'10','paid_amount':'70',
                       'paid_currency':'CNY','confirmed':True,'actor':'b'*32}

    def tearDown(self):
        self.temp.cleanup()

    def panel(self, method, path, token=None, body=None, idempotency=None):
        self.calls.append((method,path,body))
        if path == '/auth/login':
            return {'access_token':'synthetic-session'}
        if path == '/user/profile':
            return {'id':12,'balance':self.balance,'email':'private-user','password':'private'}
        if path.startswith('/usage/stats'):
            return {'total_actual_cost':self.cost}
        if path == '/admin/users/12':
            if method=='GET':return {'group_rates':self.rates}
            self.rates = body['group_rates']
            self.assertNotIn('balance',body)
            return {'group_rates':body['group_rates']}
        if path == '/admin/users/12/balance':
            self.assertEqual(body['operation'],'subtract');self.assertEqual(body['balance'],1)
            self.balance-=Decimal(str(body['balance']));return {'balance':self.balance}
        if path == '/admin/redeem-codes/create-and-redeem':
            self.assertLessEqual(len(body['code']),32)
            self.assertEqual(idempotency, body['code'])
            if body['code'] not in self.codes:
                self.balance += Decimal(str(body['value']))
                self.codes[body['code']] = {'id':77,'used_by':12,'value':body['value'],'status':'used'}
            if self.lose_response:
                self.lose_response = False
                raise BillingError('uncertain response',503)
            return {'redeem_code':self.codes[body['code']]}
        if path.startswith('/usage?'):
            return {'page':1,'pages':2,'total':21,'items':[{'id':1,'created_at':'2026-10-23T00:00:00Z',
                'model':'gpt-6.1-sol','input_tokens':10,'output_tokens':5,'cache_read_tokens':20,
                'cache_creation_tokens':0,'actual_cost':Decimal('.0025'),'rate_multiplier':Decimal('.5'),
                'api_key':{'key':'never-export'},'account_id':9,'ip_address':'private'}]}
        raise AssertionError(path)

    def activate(self):
        with patch('tokenbot.customer_billing.account_lock',lambda *a,**k:nullcontext()):
            return self.billing.activate(self.cid,self.cfg,lambda:None)

    def test_activation_removes_synthetic_balance_once_and_preserves_history(self):
        self.activate()
        self.assertEqual(self.balance,0)
        self.assertEqual(self.cfg['billing']['status'],'active')
        self.assertEqual(self.rates, {'5': 0.3335, '4': 0.3335})
        self.billing.credit(self.cid,self.cfg,self.credit)
        self.activate()
        self.assertEqual(self.balance,10)
        self.assertEqual(sum(m=='PUT' and p=='/admin/users/12' for m,p,_ in self.calls),1)

    def test_unknown_existing_balance_is_never_erased(self):
        self.balance = Decimal('25')
        with self.assertRaises(BillingError):self.activate()
        self.assertEqual(self.balance,25)
        self.assertNotIn('billing',self.cfg)

    def test_interrupted_activation_keeps_account_blocked_and_retry_is_safe(self):
        original=self.billing.panel_factory
        def failing(*args,**kwargs):
            if args[1]=='/admin/users/12':raise BillingError('native unavailable',503)
            return self.panel(*args,**kwargs)
        self.billing.panel_factory=lambda:failing
        with self.assertRaises(BillingError):self.activate()
        self.assertEqual(self.cfg['billing']['status'],'activating')
        with self.assertRaises(BillingError):self.billing.credit(self.cid,self.cfg,self.credit)
        self.billing.panel_factory=original;self.activate()
        self.assertEqual(self.cfg['billing']['status'],'active');self.assertEqual(self.balance,0)

    def test_unconfirmed_zero_balance_never_enables_billing(self):
        def ignored(*args,**kwargs):
            if args[1]=='/admin/users/12/balance':return {'balance':1}
            return self.panel(*args,**kwargs)
        self.billing.panel_factory=lambda:ignored
        with self.assertRaises(BillingError):self.activate()
        self.assertEqual(self.cfg['billing']['status'],'activating')

    def test_credit_retries_and_restart_after_lost_response_do_not_double_credit(self):
        self.activate()
        self.lose_response=True
        with self.assertRaises(BillingError):self.billing.credit(self.cid,self.cfg,self.credit)
        self.assertEqual(self.balance,10)
        restarted=CustomerBilling(self.root,lambda:self.panel)
        result=restarted.credit(self.cid,self.cfg,{**self.credit,'credit_usd':'10.00'})
        self.assertTrue(result['replayed'])
        self.assertEqual(self.balance,10)
        self.assertEqual(restarted.state(self.cid)['orders'][self.credit['reference']]['status'],'credited')
        result=restarted.credit(self.cid,self.cfg,self.credit)
        self.assertTrue(result['replayed']);self.assertEqual(self.balance,10)

    def test_changed_order_amount_or_missing_confirmation_cannot_add_money(self):
        self.activate();self.billing.credit(self.cid,self.cfg,self.credit)
        for change in ({'credit_usd':'20'},{'paid_currency':'USD'},{'confirmed':False}):
            with self.assertRaises(BillingError):self.billing.credit(self.cid,self.cfg,{**self.credit,**change})
        self.assertEqual(self.balance,10)

    def test_scope_and_money_allowlist(self):
        self.activate();self.billing.credit(self.cid,self.cfg,self.credit);self.cost=Decimal('.0025')
        data=self.billing.view(self.cid,self.cfg)
        self.assertEqual(data['spent_usd'],'0.0025')
        self.assertEqual(data['credited_usd'],'10.00')
        self.assertEqual(data['pages'],2)
        self.assertEqual(data['items'][0]['amount_usd'],'0.0025')
        self.assertNotIn('private',json.dumps(data));self.assertNotIn('never-export',json.dumps(data))
        for page in (0,-1,True,'2',10001):
            with self.assertRaises(BillingError):self.billing.view(self.cid,self.cfg,page)

    def test_invalid_amounts_are_not_silently_zero(self):
        for value in ('NaN','Infinity',True,None):
            with self.assertRaises(BillingError):amount(value)
        for value in ('0','-1','0.001','1e3',1):
            with self.assertRaises(BillingError):amount(value,True)

    def test_cny_one_to_one_policy_preserves_old_orders_and_validates_new_credit(self):
        self.activate()
        self.billing.credit(self.cid,self.cfg,self.credit)
        (self.root/'private/pricing-policy.json').write_text('{"cny_per_credit":"1"}')
        self.assertTrue(self.billing.credit(self.cid,self.cfg,self.credit)['replayed'])
        different={**self.credit,'reference':'payment-new-order','paid_currency':'CNY','paid_amount':'70'}
        with self.assertRaises(BillingError):
            self.billing.credit(self.cid,self.cfg,different)
        self.billing.credit(self.cid,self.cfg,{**different,'credit_usd':'70'})
        self.assertEqual(self.balance,80)

    def test_activation_and_view_use_configured_multiplier(self):
        with patch('tokenbot.customer_billing.account_lock',lambda *a,**k:nullcontext()):
            result=self.billing.activate(self.cid,self.cfg,lambda:None,multiplier='0.6')
        self.assertEqual(result['multiplier'],'0.6')
        self.assertEqual(self.billing.view(self.cid,self.cfg)['multiplier'],'0.6')

    def test_trial_budget_is_native_metered_without_payment_and_cannot_duplicate(self):
        self.cfg['credit_reservations']={'existing-reserve':{'amount_minor':20000}}
        grant=lambda:self.billing.grant_trial(self.cid,self.cfg,lambda:None,'200','trial-customer-001')
        grant();grant()
        self.assertEqual(self.balance,Decimal('200'))
        self.assertEqual(self.rates,{'5':.3335,'4':.3335})
        order=self.billing.state(self.cid)['orders']['trial-customer-001']
        self.assertEqual(order['paid_amount'],'0.00')
        self.assertEqual(order['kind'],'trial_credit')
        self.cost=Decimal('.0025');self.balance-=self.cost
        view=self.billing.view(self.cid,self.cfg)
        self.assertFalse(view['billing_enabled']);self.assertTrue(view['trial_budget'])
        self.assertEqual(view['balance_usd'],'199.9975')
        self.assertEqual(view['spent_usd'],'0.0025');self.assertEqual(view['cash_debited'],'0')
        self.assertEqual(view['items'][0]['status'],'trial_usage')
        self.assertEqual(self.cfg['credit_reservations']['existing-reserve']['amount_minor'],20000)
        with self.assertRaises(BillingError):self.billing.credit(self.cid,self.cfg,self.credit)
        for limit,ref in [('201','trial-customer-001'),('200','trial-customer-002')]:
            with self.assertRaises(BillingError):
                self.billing.grant_trial(self.cid,self.cfg,lambda:None,limit,ref)

    def test_trial_grant_lost_response_retries_once_and_paid_account_is_not_overwritten(self):
        self.lose_response=True
        with self.assertRaises(BillingError):
            self.billing.grant_trial(self.cid,self.cfg,lambda:None,'200','trial-retry-001')
        self.billing.grant_trial(self.cid,self.cfg,lambda:None,'200','trial-retry-001')
        self.assertEqual(self.balance,Decimal('200'))
        self.cfg['billing'].pop('mode')
        with self.assertRaises(BillingError):
            self.billing.grant_trial(self.cid,self.cfg,lambda:None,'200','trial-retry-001')

    @unittest.skipUnless(__import__('os').name=='posix','Production uses POSIX flock')
    def test_activation_requires_no_inflight_request(self):
        with account_lock(self.cfg):
            with self.assertRaises(BillingError) as error:
                with account_lock(self.cfg,exclusive=True):pass
        self.assertEqual(error.exception.status,409)


if __name__ == '__main__':
    unittest.main()
