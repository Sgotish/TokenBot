#!/usr/bin/env python3
"""Prepare one private, limited partner trial. Does not open a network listener."""
import json
import os
from pathlib import Path
import secrets
import time
from check_local_access import panel, ROOT


def main():
    os.umask(0o077)
    statefile=ROOT/'.runtime/partner-provision.json'
    if statefile.exists():
        raise SystemExit('Existing trial state retained; inspect before changing or creating another.')
    cfg=json.loads((ROOT/'.runtime/local.json').read_text())
    admin=panel('POST','/auth/login',body={'email':cfg['admin_email'],'password':cfg['admin_password']})['access_token']
    accounts=[panel('GET','/admin/accounts/'+str(i),admin) for i in (1,2)]
    if any(a['type']!='oauth' or a['platform']!='openai' or a['status']!='active' for a in accounts):
        raise SystemExit('Subscription fixtures changed; no edits made')
    state={'created_at':time.time(),'original_groups':{},'scope':'private partner trial; synthetic internal credit, no payment'}
    def save():
        statefile.write_text(json.dumps(state));statefile.chmod(0o600)
    save()
    group=panel('POST','/admin/groups',admin,{'name':'搭档私有测试 · 双订阅',
        'description':'Temporary internal connectivity trial; not a commercial plan',
        'platform':'openai','rate_multiplier':1,'is_exclusive':True,
        'subscription_type':'standard','require_oauth_only':True,
        'allow_image_generation':False,'allow_batch_image_generation':False})
    state['group_id']=group['id'];save()
    for a in accounts:
        old=a.get('group_ids') or [g['id'] for g in a.get('groups',[])]
        state['original_groups'][str(a['id'])]=old;save()
        panel('PUT','/admin/accounts/'+str(a['id']),admin,{'group_ids':list(dict.fromkeys(old+[group['id']]))})
    password=secrets.token_urlsafe(32)
    user=panel('POST','/admin/users',admin,{'email':'partner-test-'+secrets.token_hex(5)+'@example.com',
        'password':password,'username':'搭档受限测试','notes':'Internal trial only; synthetic balance',
        'role':'user','balance':1,'concurrency':1,'rpm_limit':6,
        'allowed_groups':[group['id']],'restrict_public_groups':True})
    state.update(user_id=user['id'],email=user['email'],password=password);save()
    customer=panel('POST','/auth/login',body={'email':user['email'],'password':password})['access_token']
    key=panel('POST','/keys',customer,{'name':'Private partner trial','group_id':group['id'],
        'quota':1,'expires_in_days':1,'ip_whitelist':['127.0.0.1/32']})
    state['key_id']=key['id'];save()
    trial={'key':key['key'],'expires_at':time.time()+86400,'allowed_ips':['127.0.0.1'],
           'user_id':user['id'],'group_id':group['id'],'key_id':key['id']}
    dest=ROOT/'.runtime/partner-test.json';dest.write_text(json.dumps(trial));dest.chmod(0o600)
    print(json.dumps({'prepared':True,'group_id':group['id'],'user_id':user['id'],
                      'key_id':key['id'],'network_listener_opened':False}))


if __name__=='__main__':main()
