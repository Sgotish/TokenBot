#!/usr/bin/env python3
"""Bounded model/effort forwarding check. Fixed synthetic question; no retries."""
import argparse
import json
import time
from pathlib import Path
import httpx
from tokenbot.model_catalog import MODEL_EFFORTS


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True,type=Path);p.add_argument('--report',required=True,type=Path)
    p.add_argument('--origin',default='http://127.0.0.1:8183');p.add_argument('--matrix',action='store_true')
    a=p.parse_args();cfg=json.loads(a.config.read_text())
    cases=[(m,e) for m,efforts in MODEL_EFFORTS.items() for e in (tuple(e for e in efforts if e != 'ultra') if a.matrix else ('low',))]
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with httpx.Client(trust_env=False,follow_redirects=False,timeout=90) as client,a.report.open('x') as out:
        for model,effort in cases:
            start=time.monotonic();text='';done=None;failure=None;status=None
            try:
                with client.stream('POST',a.origin+'/v1/responses',headers={'Authorization':'Bearer '+cfg['key']},json={
                    'model':model,'reasoning':{'effort':effort},'stream':True,'store':False,
                    'instructions':'Answer the arithmetic question only. Do not use tools.',
                    'input':[{'role':'user','content':'What is 17+25? Reply only 42.'}]}) as response:
                    status=response.status_code
                    if status==200:
                        for line in response.iter_lines():
                            if not line.startswith('data: {'):continue
                            event=json.loads(line[6:])
                            if event.get('type')=='response.output_text.delta':text+=event.get('delta','')
                            elif event.get('type')=='response.completed':done=event.get('response',{})
                            elif event.get('type') in ('error','response.failed','response.incomplete'):failure=event.get('type')
                    else:
                        body=response.read()
                        try:failure=json.loads(body).get('error',{}).get('message','upstream error')[:240]
                        except Exception:failure='upstream error'
            except Exception as e:failure=type(e).__name__
            row={'model_requested':model,'effort_requested':effort,'model_returned':(done or {}).get('model'),
                 'reasoning_returned':(done or {}).get('reasoning'),'http':status,'text':text[:100],
                 'completed':(done or {}).get('status')=='completed','seconds':round(time.monotonic()-start,3),
                 'error':failure,'usage':(done or {}).get('usage')}
            row['pass']=status==200 and row['completed'] and text.strip()=='42' and failure is None
            out.write(json.dumps(row)+'\n');out.flush();print(json.dumps({k:v for k,v in row.items() if k!='usage'}),flush=True)
            if not row['pass']:raise SystemExit('Stopped on first failure; no automatic retry.')

if __name__=='__main__':main()
