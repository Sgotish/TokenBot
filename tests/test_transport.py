import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from tokenbot.client import Client
from tokenbot.economics import calculate

class Transport(unittest.TestCase):
    def test_redirect_never_forwards_key(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.path)
                if self.path=='/v1/models':
                    self.send_response(302);self.send_header('Location','/untrusted');self.end_headers()
                else:self.send_response(200);self.end_headers()
            def log_message(self,*a):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            client=Client('http://127.0.0.1:'+str(server.server_port)+'/v1','private-test-key')
            status,_,_=client.request('GET','/models')
            self.assertEqual(status,302);self.assertEqual(seen,['/v1/models'])
        finally:server.shutdown();server.server_close();thread.join()
    def test_revenue_not_deposits(self):
        data={'currency':'TEST','period':'month','deposits_received':'2000','earned_revenue':'1200','upstream_api_cost':'200','subscription_cost':'300','hosting_cost':'100','maintenance_cost':'150','payment_fees':'20','refund_cost':'30'}
        result=calculate(data)
        self.assertEqual(result['total_cost'],'800.00');self.assertEqual(result['operating_result'],'400.00')
        data['deposits_received']='99999';self.assertEqual(calculate(data)['operating_result'],'400.00')
    def test_no_revenue_margin_unknown(self):
        data={k:'0' for k in ('deposits_received','earned_revenue','upstream_api_cost','subscription_cost','hosting_cost','maintenance_cost','payment_fees','refund_cost')}
        self.assertIsNone(calculate({**data,'currency':'TEST','period':'month'})['margin_rate'])
