import json
from pathlib import Path
import tempfile
import time
import unittest
from decimal import Decimal
from tokenbot.usage import normalize, amount, summarize
from tokenbot.queue import Queue
from tokenbot.client import Client

DONE={'status':'completed','error':None,'output':[], 'usage':{'input_tokens':1000,'output_tokens':100,'input_tokens_details':{'cached_tokens':600,'cache_write_tokens':100}}}
RATES={'uncached':'2','cache_read':'0.2','cache_write':'2.5','output':'8'}

def item(ident='a',text='Synthetic lead to classify'):
    return {'custom_id':ident,'method':'POST','url':'/v1/responses','body':{'model':'test-model','input':text}}

class Fake:
    base='https://example.com/v1';key='fake-test-key'
    def __init__(self,status=200,body=None,headers=None):
        self.status=status;self.body=DONE if body is None else body;self.headers=headers or {};self.calls=0
    def request(self,*args):
        self.calls+=1
        return self.status,self.headers,json.dumps(self.body).encode()

class Operations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.q=Queue(Path(self.tmp.name)/'queue.sqlite')
    def tearDown(self):self.q.db.close();self.tmp.cleanup()
    def test_inclusive_cache_counts(self):
        u=normalize(DONE)
        self.assertEqual(u,{'input_total':1000,'output':100,'cache_read':600,'cache_write':100,'uncached':300})
        self.assertEqual(amount(u,RATES),Decimal('0.00177'))
    def test_anthropic_exclusive_counts(self):
        u=normalize({'usage':{'input_tokens':300,'output_tokens':100,'cache_read_input_tokens':600,'cache_creation_input_tokens':100}})
        self.assertEqual(u,normalize(DONE))
    def test_unknown_cache_is_not_zero(self):
        u=normalize({'usage':{'input_tokens':1000,'output_tokens':100}})
        self.assertIsNone(u['cache_read']);self.assertIsNone(amount(u,RATES))
    def test_missing_usage(self):self.assertIsNone(normalize({'status':'completed'}))
    def test_invalid_counts(self):
        for v in (-1,True,1.2):
            with self.assertRaises(ValueError):normalize({'usage':{'input_tokens':v,'output_tokens':1}})
    def test_cache_cannot_exceed_total(self):
        with self.assertRaises(ValueError):normalize({'usage':{'input_tokens':1,'output_tokens':1,'input_tokens_details':{'cached_tokens':2}}})
    def test_finite_prices(self):
        for v in ('NaN','Infinity','-1'):
            with self.assertRaises(ValueError):amount(normalize(DONE),{**RATES,'uncached':v})
    def test_cost_coverage_excludes_unknown(self):
        rows=[{'model':'test-model','status':'succeeded','usage':normalize(DONE)},{'model':'test-model','status':'succeeded','usage':None}]
        out=summarize(rows,{'currency':'USD','models':{'test-model':{'cost':RATES,'sell':RATES}}})
        self.assertEqual(out['priced_successes'],1);self.assertEqual(out['unpriced_successes'],1);self.assertFalse(out['complete'])
        self.assertEqual(out['cache_read_hit_rate'],0.6)
    def test_idempotent_import(self):
        self.assertEqual(self.q.enqueue([item()]),1);self.assertEqual(self.q.enqueue([item()]),0)
        with self.assertRaises(ValueError):self.q.enqueue([item(text='different')])
    def test_atomic_import(self):
        self.q.enqueue([item()])
        with self.assertRaises(ValueError):self.q.enqueue([item('b'),item(text='different')])
        self.assertEqual(len(self.q.metrics()),1)
    def test_reject_remote_context(self):
        for field in ('previous_response_id','conversation','stream','background'):
            row=item();row['body'][field]='x'
            with self.assertRaises(ValueError):self.q.enqueue([row])
    def test_success_null_error_and_no_replay(self):
        self.q.enqueue([item()]);client=Fake();self.assertTrue(self.q.run_one(client));self.assertFalse(self.q.run_one(client))
        self.assertEqual(client.calls,1);self.assertEqual(self.q.metrics()[0]['status'],'succeeded')
    def test_timeout_never_auto_retried(self):
        self.q.enqueue([item()]);client=Fake(0);self.q.run_one(client)
        self.assertEqual(self.q.metrics()[0]['status'],'uncertain');self.assertFalse(self.q.run_one(client))
    def test_server_error_never_auto_retried(self):
        self.q.enqueue([item()]);self.q.run_one(Fake(502));self.assertEqual(self.q.metrics()[0]['status'],'uncertain')
    def test_rate_limit_waits_and_caps_attempts(self):
        self.q.enqueue([item()]);client=Fake(429,headers={'Retry-After':'60'})
        self.q.run_one(client);self.assertFalse(self.q.run_one(client));self.assertEqual(client.calls,1)
        for _ in range(3):
            self.q.db.execute('UPDATE jobs SET available_at=0');self.q.run_one(client)
        self.assertEqual(client.calls,4);self.assertEqual(self.q.metrics()[0]['status'],'failed')
    def test_empty_error_is_failure(self):
        self.q.enqueue([item()]);self.q.run_one(Fake(body={**DONE,'error':{}}));self.assertEqual(self.q.metrics()[0]['status'],'failed')
    def test_incomplete_is_uncertain(self):
        self.q.enqueue([item()]);self.q.run_one(Fake(body={**DONE,'status':'incomplete'}));self.assertEqual(self.q.metrics()[0]['status'],'uncertain')
    def test_target_binding(self):
        self.q.enqueue([item(),item('b')]);self.q.run_one(Fake());c=Fake();c.key='different'
        with self.assertRaises(ValueError):self.q.run_one(c)
        self.assertEqual(c.calls,0)
    def test_metrics_do_not_include_content(self):
        self.q.enqueue([item(text='PRIVATE-PROMPT')]);self.q.run_one(Fake())
        self.assertNotIn('PRIVATE-PROMPT',json.dumps(self.q.metrics()));self.assertNotIn('output',self.q.metrics()[0])
    def test_crash_recovery_requires_review(self):
        self.q.enqueue([item()]);self.q.claim();self.q.db.execute('UPDATE jobs SET updated_at=?',(time.time()-1000,))
        self.assertEqual(self.q.recover(900),1);self.assertEqual(self.q.metrics()[0]['status'],'uncertain')
    def test_two_workers_claim_separately(self):
        self.q.enqueue([item(),item('b')]);q2=Queue(Path(self.tmp.name)/'queue.sqlite')
        self.assertNotEqual(self.q.claim()['id'],q2.claim()['id']);self.assertIsNone(q2.claim());q2.db.close()
    def test_client_rejects_credentials_in_url(self):
        for url in ('http://remote.example/v1','https://user:pass@example.com/v1','https://example.com/v1?key=x'):
            with self.assertRaises(ValueError):Client(url,'test')

if __name__=='__main__':unittest.main()
