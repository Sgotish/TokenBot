#!/usr/bin/env python3
"""Enable/disable exactly one cloud customer without touching anyone else's key."""
import argparse
import fcntl
import grp
import json
from provision_cloud_client import ROOT, save

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('client_id')
    mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--enable',action='store_true');mode.add_argument('--disable',action='store_true')
    a=p.parse_args()
    private=ROOT/'private'
    with (private/'provision.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        config=json.loads((private/'partner.json').read_text())
        from pathlib import Path
        path=Path(config['clients_path']);registry=json.loads(path.read_text())
        if a.client_id not in registry['clients']:raise SystemExit('Unknown customer; nothing changed')
        registry['clients'][a.client_id]['enabled']=a.enable
        save(path,registry,0o640,grp.getgrnam('tokenbot-bridge').gr_gid)
        print(json.dumps({'client_id':a.client_id,'enabled':a.enable}))
if __name__=='__main__':main()
