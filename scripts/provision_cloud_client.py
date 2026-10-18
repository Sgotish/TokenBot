#!/usr/bin/env python3
"""Run on the authorized cloud host. Issue one private customer identity, never print keys."""
import argparse
import fcntl
import grp
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import urllib.request

ROOT = Path('/opt/tokenbot-pilot')

def save(path, data, mode=0o600, group=None):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.chmod(mode)
    if group is not None:
        os.chown(tmp, 0, group)
    tmp.replace(path)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('client_id');p.add_argument('--label',required=True)
    p.add_argument('--upstream-cidr',action='append',required=True,
                   help='Exact bridge source network as seen by the upstream container')
    a=p.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,39}',a.client_id) or a.client_id=='partner':
        p.error('Use a unique lowercase client id, 3-40 characters')
    os.umask(0o077)
    allowed_ips=[str(ipaddress.ip_network(cidr,strict=True)) for cidr in a.upstream_cidr]
    gid=grp.getgrnam('tokenbot-bridge').gr_gid
    private=ROOT/'private'; customers=private/'customers';customers.mkdir(exist_ok=True)
    with (private/'provision.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        config=json.loads((private/'partner.json').read_text())
        collector=json.loads((private/'collector.json').read_text())
        registry_path=Path(config['clients_path'])
        registry=json.loads(registry_path.read_text())
        if a.client_id in registry['clients']:
            raise SystemExit('Client already exists; use its existing private handoff or explicitly rotate it.')
        state_path=customers/(a.client_id+'.json')
        state=json.loads(state_path.read_text()) if state_path.exists() else {
            'partner':{'email':'tokenbot-'+a.client_id+'@example.com','password':secrets.token_urlsafe(32)},
            'keys':{},'key':'tb_'+secrets.token_urlsafe(36),'label':a.label}
        save(state_path,state)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def panel(method,path,token=None,body=None):
            req=urllib.request.Request('http://127.0.0.1:8180/api/v1'+path,method=method,
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
            with opener.open(req,timeout=30) as response:result=json.load(response)
            if result.get('code')!=0:raise RuntimeError('Panel request failed')
            return result['data']
        admin=panel('POST','/auth/login',body=collector['admin'])['access_token']
        if not state.get('user_id'):
            user=panel('POST','/admin/users',admin,{**state['partner'],'username':a.label,
                'role':'user','balance':1,'concurrency':2,'rpm_limit':0,
                'allowed_groups':[pool['group_id'] for pool in config['pools'].values()],
                'restrict_public_groups':True,'notes':'Private isolated pilot customer; no payment collected'})
            state['user_id']=user['id'];save(state_path,state)
        token=panel('POST','/auth/login',body=state['partner'])['access_token']
        existing=panel('GET','/keys?page=1&page_size=100',token)['items']
        for name,pool in config['pools'].items():
            if name not in state['keys']:
                title='TokenBot '+a.client_id+' '+name
                matches=[k for k in existing if k['name']==title]
                key=matches[0] if len(matches)==1 else panel('POST','/keys',token,{
                    'name':title,'group_id':pool['group_id'],'quota':0,'ip_whitelist':allowed_ips})
                state['keys'][name]={'key':key['key'],'id':key['id']};save(state_path,state)
        client_root=Path('/var/lib/tokenbot-bridge/clients')
        client_root.mkdir(exist_ok=True);os.chown(client_root,0,gid);client_root.chmod(0o750)
        dest=client_root/a.client_id
        dest.mkdir(exist_ok=True);os.chown(dest,0,gid);dest.chmod(0o770)
        snapshot=Path('/var/lib/tokenbot-status')/(a.client_id+'.json')
        customer={'key':state['key'],'label':a.label,'enabled':True,'expires_at':None,
            'selection_path':str(dest/'selection.json'),'snapshot_path':str(snapshot),
            'pools':{name:{**pool,'key':state['keys'][name]['key']} for name,pool in config['pools'].items()}}
        state.update(snapshot_path=str(snapshot),accounts=collector['accounts'],groups=collector['groups'])
        save(state_path,state)
        save(snapshot,{'generated_at':None,'accounts':[],'records':[],'totals':{}},0o640,gid)
        registry['clients'][a.client_id]=customer;save(registry_path,registry,0o640,gid)
        save(customers/(a.client_id+'.handoff'),{'client_id':a.client_id,'label':a.label,
             'key':state['key'],'public_origin':config['public_origin'],'base_url':config['public_origin']+'/v1'})
        print(json.dumps({'client_id':a.client_id,'user_id':state['user_id'],'created':True,'credentials_printed':False}))

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('Provisioning stopped; private recovery state retained. No credentials printed.')
