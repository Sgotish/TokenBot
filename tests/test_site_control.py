import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile
from fastapi.testclient import TestClient
from tokenbot.site_control import SiteControl, ControlError, create_app
from tokenbot.partner_portal import ClientRegistry

class SiteControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        (self.root/'private').mkdir()
        self.reg=self.root/'private/clients.json';self.reg.write_text('{"clients":{}}')
        self.main={'key':'partner-original-secret','expires_at':None,'clients_path':str(self.reg),'public_origin':'https://pilot.tokenbots.top'}
        (self.root/'private/partner.json').write_text(json.dumps(self.main))
        def provision(cid):
            snap=self.root/(cid+'.snapshot');snap.write_text(json.dumps({'generated_at':123,'records':[{'model':cid}]}))
            data=json.loads(self.reg.read_text());data['clients'][cid]={'key':'upstream-'+cid,'expires_at':None,'enabled':True,
                'selection_path':str(self.root/(cid+'.selection')),'snapshot_path':str(snap),'pools':{'auto':{'key':'pool-'+cid,'label':'auto'}}}
            self.reg.write_text(json.dumps(data))
        self.c=SiteControl(self.root,'secret-'+'x'*50,provision)
        self.a='a'*32;self.b='b'*32
    def tearDown(self): self.tmp.cleanup()
    def issue(self,uid,kid='c'*32):return self.c.run('create-key',{'uid':uid,'request_id':kid,'label':'desktop'})
    def test_isolation_revocation_idempotency(self):
        a=self.issue(self.a);b=self.issue(self.b)
        self.assertEqual(a,self.issue(self.a));self.assertNotEqual(a['api_key'],b['api_key'])
        reg=ClientRegistry(self.main)
        self.assertEqual(reg.resolve(key=a['api_key'])[0],'web-'+self.a)
        self.assertEqual(reg.resolve(key=b['api_key'])[0],'web-'+self.b)
        public=self.c.run('status',{'uid':self.b})
        self.assertNotIn(a['api_key'],str(public));self.assertNotIn('digest',str(public))
        with self.assertRaises(ControlError):self.c.run('package',{'uid':self.b,'api_key':a['api_key']})
        other=self.issue(self.a,'d'*32)
        self.c.run('revoke-key',{'uid':self.a,'id':a['id']})
        self.assertIsNone(reg.resolve(key=a['api_key']))
        self.assertIsNotNone(reg.resolve(key=other['api_key']))
        self.assertIsNotNone(reg.resolve(key=b['api_key']))
        self.c.run('set-enabled',{'uid':self.b,'enabled':False})
        self.assertIsNone(reg.resolve(key=b['api_key']))
        self.assertIsNotNone(reg.resolve(key=self.main['key']))
    def test_auth_and_bad_input(self):
        with TestClient(create_app(self.c)) as client:
            self.assertEqual(client.post('/internal/site/status',json={'uid':self.a}).status_code,401)
            h={'Authorization':'Bearer '+self.c.secret}
            self.assertEqual(client.post('/internal/site/status',json={'uid':'../../etc'},headers=h).status_code,400)
            self.assertEqual(client.post('/internal/site/status',content='x'*5000,headers=h).status_code,413)
            self.assertFalse(client.post('/internal/site/status',json={'uid':self.a},headers=h).json()['configured'])
    def test_usage_report_owner_binding_and_missing_data(self):
        self.c.research_state=self.root/'research';self.c.research_state.mkdir()
        (self.c.research_state/'customers').mkdir()
        (self.root/'private/customers').mkdir()
        self.assertFalse(self.c.run('usage-visualization',{'uid':self.a})['configured'])
        self.issue(self.a);self.issue(self.b)
        for uid,user_id in [(self.a,101),(self.b,202)]:
            cid='web-'+uid
            (self.root/'private/customers'/(cid+'.json')).write_text(json.dumps({'user_id':user_id}))
            (self.c.research_state/'customers'/(cid+'.json')).write_text(json.dumps({
                'owner_user_id':user_id,'visualization':{'generated_at':1,'periods':[{'tokens':user_id}]}}))
        data=self.c.run('usage-visualization',{'uid':self.a})
        self.assertEqual(data['periods'],[{'tokens':101}]);self.assertTrue(data['stale'])
        self.assertNotIn('owner_user_id',data)
        (self.root/'private/customers'/('web-'+self.a+'.json')).write_text('{"user_id":202}')
        with self.assertRaises(ControlError) as error:self.c.run('usage-visualization',{'uid':self.a})
        self.assertEqual(error.exception.status,503)
        with self.assertRaises(ControlError):self.c.run('admin-research',{'uid':self.a})
        (self.c.research_state/'report.json').write_text('{"generated_at":1,"accounts":[]}')
        self.assertTrue(self.c.run('admin-research',{'uid':self.a})['report_stale'])
    def test_private_bundle(self):
        source=Path(__file__).resolve().parents[1]
        for rel in ['integrations/codex-client/dist/tokenbots.cjs','integrations/codex-client/node_modules/smol-toml/LICENSE']:
            dest=self.root/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('packaging fixture')
        for rel in ['integrations/windows-codex/setup.ps1.template']:
            dest=self.root/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/rel,dest)
        shutil.copytree(source/'integrations/windows-codex/native-menu',self.root/'integrations/windows-codex/native-menu')
        a=self.issue(self.a)
        with zipfile.ZipFile(io.BytesIO(self.c.package('web-'+self.a,a['api_key']))) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(json.loads(z.read('TokenBots/access.json'))['key'],a['api_key'])
            self.assertIn('TokenBots/install-native.cmd',z.namelist())
            launch=z.read('TokenBots/install-native.cmd').decode()
            self.assertIn('native-menu\\install.ps1',launch)
            self.assertNotIn('-File setup.ps1',launch)  # no pre-install write to the user's default home
            self.assertIn('TokenBots/setup-cli.command',z.namelist())
            self.assertIn('TokenBots/start-cli.command',z.namelist())
            self.assertIn('run --',z.read('TokenBots/start-cli.command').decode())
            self.assertNotIn(self.c.secret,str([z.read(n) for n in z.namelist()]))

if __name__=='__main__':unittest.main()
