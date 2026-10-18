#!/usr/bin/env python3
"""Run bounded Guangdong Globalping probes; never transmit customer API keys."""
import argparse
import json
import time
import urllib.request
from pathlib import Path

NETWORKS={'Guangzhou':4134,'Dongguan':4134,'Shenzhen':17962}

def api(path, body=None):
    req=urllib.request.Request('https://api.globalping.io/v1/'+path,
        json.dumps(body).encode() if body is not None else None,
        {'Content-Type':'application/json','User-Agent':'TokenBot-Guangdong-QA/1.0'})
    with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)

def assess(data, city, mode):
    results=data.get('results',[])
    if len(results)!=1:return {'pass':False,'reason':'probe_count','count':len(results)}
    probe=results[0]['probe'];r=results[0]['result'];raw=r.get('rawBody') or ''
    completed=[];answer=''
    for block in raw.split('\n\n'):
        lines=block.splitlines();event=next((s[7:] for s in lines if s.startswith('event: ')),None)
        payload=next((s[6:] for s in lines if s.startswith('data: ')),None)
        if payload:
            try:value=json.loads(payload)
            except ValueError:continue
            if event=='completed':completed.append(value)
            if event=='text':answer+=value.get('delta','')
    expected='42' if mode=='answer' else '\n'.join(map(str,range(1,81)))+'\nEND-GD'
    location_ok=probe.get('country')=='CN' and probe.get('city')==city and probe.get('asn')==NETWORKS[city]
    duration_ok=(mode!='stream' or (len(completed)==1 and completed[0].get('total_seconds',0)>=20
                 and r.get('timings',{}).get('total',0)>=20000))
    passed=(data.get('status')=='finished' and r.get('status')=='finished' and duration_ok
            and location_ok and r.get('statusCode')==200 and not r.get('truncated') and len(completed)==1
            and completed[0].get('pass') is True and completed[0].get('upstream_completed') is True
            and answer.strip()==expected and r.get('tls',{}).get('authorized') is True)
    return {'pass':passed,'city':probe.get('city'),'asn':probe.get('asn'),'network':probe.get('network'),
            'tags':probe.get('tags'),'location_verified':location_ok,'http':r.get('statusCode'),
            'timings_ms':r.get('timings'),'completed':completed,'body_truncated':r.get('truncated'),
            'answer_verified':answer.strip()==expected,'status':r.get('status'),'tls_verified':r.get('tls',{}).get('authorized')}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();cases=json.loads(args.manifest.read_text())['cases'];args.output.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for mode in ('answer','stream'):
        for city,asn in NETWORKS.items():
            caps=[k for k,v in cases.items() if v['label']==city+'-'+mode and v['mode']==mode]
            if len(caps)!=1:raise SystemExit('Manifest does not contain exactly one requested case')
            started=api('measurements',{'type':'http','target':'pilot.tokenbots.top','timeout':30,
                'locations':[{'country':'CN','city':city,'asn':asn,'limit':1}],
                'measurementOptions':{'request':{'method':'GET','path':'/network-check/'+caps[0]}}})
            ident=started['id'];deadline=time.monotonic()+55
            while True:
                data=api('measurements/'+ident)
                if data['status']!='in-progress':break
                if time.monotonic()>deadline:raise SystemExit('Measurement polling deadline reached; inspect existing ID before retrying')
                time.sleep(2)
            (args.output/(city+'-'+mode+'.json')).write_text(json.dumps(data,ensure_ascii=False))
            summary={'measurement':ident,'case':city+'-'+mode,**assess(data,city,mode)}
            summaries.append(summary);(args.output/'summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2))
            print(json.dumps(summary,ensure_ascii=False),flush=True)
            if not summary['pass']:
                raise SystemExit('Probe failed; remaining model calls stopped. Inspect the saved report before retrying.')
    if not all(s['pass'] for s in summaries):raise SystemExit('One or more Guangdong probes failed; inspect reports, do not claim acceptance')

if __name__=='__main__':main()
