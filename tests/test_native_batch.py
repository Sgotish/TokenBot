import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
from tokenbot.cli import main, update_receipt

class Provider:
    def __init__(self,failed=False):self.calls=[];self.failed=failed
    def request(self,method,path,body=None,content_type=None):
        self.calls.append((method,path))
        if path=='/files':return 200,{},b'{"id":"file-test"}'
        if path=='/batches':return (0,{},b'') if self.failed else (200,{},b'{"id":"batch_test","status":"validating"}')
        if path.endswith('/content'):return 200,{},b'{"custom_id":"a","response":{}}\n'
        if path.endswith('/cancel'):return 200,{},b'{"id":"batch_test","status":"cancelling"}'
        return 200,{},b'{"id":"batch_test","status":"completed","output_file_id":"file-test"}'

class Native(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.input=self.root/'input.jsonl';self.receipt=self.root/'receipt.json'
        self.input.write_text(json.dumps({'custom_id':'a','method':'POST','url':'/v1/responses','body':{'model':'test','input':'synthetic'}})+'\n')
    def tearDown(self):self.tmp.cleanup()
    def call(self,args,client):
        with patch('sys.argv',['tokenbot',*map(str,args)]),patch('tokenbot.cli.Client.from_env',return_value=client),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):main()
    def test_submit_and_receipt_prevents_second_submit(self):
        client=Provider();args=['provider-batch-submit',self.input,'--receipt',self.receipt,'--enabled']
        self.call(args,client);self.assertEqual(json.loads(self.receipt.read_text())['state'],'submitted')
        with self.assertRaises(SystemExit):self.call(args,client)
        self.assertEqual(client.calls,[('POST','/files'),('POST','/batches')]);self.assertEqual(self.receipt.stat().st_mode&0o777,0o600)
    def test_native_requires_explicit_enable(self):
        client=Provider()
        with self.assertRaises(SystemExit):self.call(['provider-batch-submit',self.input,'--receipt',self.receipt],client)
        self.assertEqual(client.calls,[])
    def test_timeout_keeps_receipt_and_file_id(self):
        with self.assertRaises(SystemExit):self.call(['provider-batch-submit',self.input,'--receipt',self.receipt,'--enabled'],Provider(True))
        r=json.loads(self.receipt.read_text());self.assertEqual(r['state'],'submission_uncertain');self.assertEqual(r['file_id'],'file-test')
    def test_result_download_private(self):
        out=self.root/'out.jsonl';self.call(['provider-batch-results','file-test','--out',out],Provider())
        self.assertIn('custom_id',out.read_text());self.assertEqual(out.stat().st_mode&0o777,0o600)
    def test_cancel_requires_confirmation_flag(self):
        client=Provider()
        with self.assertRaises(SystemExit):self.call(['provider-batch-cancel','batch_test'],client)
        self.assertEqual(client.calls,[])
        self.call(['provider-batch-cancel','batch_test','--confirm'],client);self.assertEqual(client.calls,[('POST','/batches/batch_test/cancel')])
    def test_mixed_models_rejected_before_upload(self):
        with self.input.open('a') as f:f.write(json.dumps({'custom_id':'b','method':'POST','url':'/v1/responses','body':{'model':'different'}}))
        client=Provider()
        with self.assertRaises(SystemExit):self.call(['provider-batch-submit',self.input,'--receipt',self.receipt,'--enabled'],client)
        self.assertEqual(client.calls,[])

    def test_invalid_or_remote_context_rejected_before_upload(self):
        for item in ([], {'custom_id':'a','method':'POST','url':'/v1/responses','body':{'model':'test'}},
                     {'custom_id':'a','method':'POST','url':'/v1/responses','body':{'model':'test','input':'x','previous_response_id':'resp_a'}}):
            with self.subTest(item=item):
                self.input.write_text(json.dumps(item));client=Provider()
                with self.assertRaises(SystemExit):self.call(['provider-batch-submit',self.input,'--receipt',self.receipt,'--enabled'],client)
                self.assertEqual(client.calls,[]);self.assertFalse(self.receipt.exists())

    def test_interrupted_receipt_update_preserves_previous_file(self):
        self.receipt.write_text('{"file_id":"file-original"}')
        with patch('tokenbot.cli.os.replace',side_effect=OSError('write interrupted')):
            with self.assertRaises(OSError):update_receipt(self.receipt,{'state':'submitted'})
        self.assertEqual(json.loads(self.receipt.read_text())['file_id'],'file-original')
        self.assertEqual(list(self.root.glob('.receipt-*')),[])
