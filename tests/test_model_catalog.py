import json
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from tokenbot.partner_gateway import create_app
from tokenbot.model_catalog import MODEL_EFFORTS


def test_all_models_and_efforts_preserved_with_no_fallback():
    calls=[]
    def upstream(req):
        calls.append(json.loads(req.content))
        return httpx.Response(200,json={'model':calls[-1]['model'],'reasoning':calls[-1].get('reasoning')})
    config={'key':'test-secret','expires_at':None,'allowed_ips':['testclient']}
    with TestClient(create_app(config,httpx.MockTransport(upstream)),headers={'Authorization':'Bearer test-secret'}) as c:
        assert [m['id'] for m in c.get('/v1/models').json()['data']]==list(MODEL_EFFORTS)
        for model,efforts in MODEL_EFFORTS.items():
            for effort in (e for e in efforts if e != 'ultra'):
                body={'model':model,'reasoning':{'effort':effort},'input':'42','stream':True}
                assert c.post('/v1/responses',json=body).status_code==200
                assert calls[-1]==body
        count=len(calls)
        for body in ({'model':'unknown'}, {'model':[]}, {'model':'gpt-6-astra','reasoning':'high'},
                     {'model':'gpt-6-astra','reasoning':{'effort':'invented'}},
                     {'model':'gpt-6-luna','reasoning':{'effort':'ultra'}},
                     {'model':'gpt-6-astra','reasoning':{'effort':'low'},'reasoning_effort':'high'}):
            assert c.post('/v1/responses',json=body).status_code==400
        assert len(calls)==count


def test_portable_catalog_matches_gateway():
    d=json.loads(Path('integrations/model-catalog/models.json').read_text())
    assert {m['id']:tuple(m['reasoning_efforts']) for m in d['models']}==MODEL_EFFORTS
