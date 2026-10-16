#!/usr/bin/env python3
"""Run an isolated macOS pilot with verified binary + local PostgreSQL/Redis.
Does not register login services, open LAN ports, accept terms, or add upstreams.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / '.runtime'
PG = Path('/opt/homebrew/opt/postgresql@16/bin')
REDIS = Path('/opt/homebrew/opt/redis/bin')
PORTS = (8180, 55439, 56389)

def run(argv, **kw):
    return subprocess.run([str(v) for v in argv], check=True, stdout=subprocess.DEVNULL, **kw)

def available(port):
    with socket.socket() as s:
        s.bind(('127.0.0.1',port))

def start(binary):
    for port in PORTS: available(port)
    lock = json.loads((ROOT/'upstream.lock.json').read_text())
    # Binary hash is written by our release installer only after verifying the archive.
    stamp = R/'binary.json'
    if not stamp.exists() or hashlib.sha256(binary.read_bytes()).hexdigest() != json.loads(stamp.read_text())['sha256']:
        raise SystemExit('Run scripts/install_release.py first; binary is not verified.')
    R.mkdir(mode=0o700,exist_ok=True)
    cfgfile = R/'local.json'
    if not cfgfile.exists():
        cfg = {k:secrets.token_hex(32) for k in ('db_password','redis_password','jwt','totp','admin_password')}
        cfg['admin_email'] = 'pilot-admin@example.com'
        fd=os.open(cfgfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f: json.dump(cfg,f)
    cfg = json.loads(cfgfile.read_text())
    pw=R/'pg-password'; pw.write_text(cfg['db_password']); pw.chmod(0o600)
    db_env = {**os.environ,'PGPASSWORD':cfg['db_password']}
    if not (R/'postgres'/'PG_VERSION').exists():
        run([PG/'initdb','-D',R/'postgres','-U','tokenbot','--auth=scram-sha-256','--pwfile',pw,'--encoding=UTF8','--locale=C'])
    pw.unlink()
    run([PG/'pg_ctl','-D',R/'postgres','-l',R/'postgres.log','-o',f'-h 127.0.0.1 -p {PORTS[1]} -k {R}','start'])
    check=subprocess.run([str(PG/'psql'),'-h','127.0.0.1','-p',str(PORTS[1]),'-U','tokenbot','-d','postgres','-tAc',"SELECT 1 FROM pg_database WHERE datname='tokenbot'"],env=db_env,capture_output=True,check=True)
    if '1' not in check.stdout.decode():
        run([PG/'createdb','-h','127.0.0.1','-p',str(PORTS[1]),'-U','tokenbot','tokenbot'],env=db_env)
    redisconf=R/'redis.conf'
    redisconf.write_text(f'bind 127.0.0.1\nport {PORTS[2]}\nrequirepass {cfg["redis_password"]}\ndir "{R}"\nappendonly yes\ndaemonize yes\npidfile "{R}/redis.pid"\nlogfile "{R}/redis.log"\n')
    redisconf.chmod(0o600)
    run([REDIS/'redis-server',redisconf])
    (R/'data').mkdir(exist_ok=True)
    env={**os.environ,'DATA_DIR':str(R/'data'),'AUTO_SETUP':'true','SERVER_HOST':'127.0.0.1','SERVER_PORT':str(PORTS[0]),'DATABASE_HOST':'127.0.0.1','DATABASE_PORT':str(PORTS[1]),'DATABASE_USER':'tokenbot','DATABASE_PASSWORD':cfg['db_password'],'DATABASE_DBNAME':'tokenbot','DATABASE_SSLMODE':'disable','REDIS_HOST':'127.0.0.1','REDIS_PORT':str(PORTS[2]),'REDIS_PASSWORD':cfg['redis_password'],'ADMIN_EMAIL':cfg['admin_email'],'ADMIN_PASSWORD':cfg['admin_password'],'JWT_SECRET':cfg['jwt'],'TOTP_ENCRYPTION_KEY':cfg['totp'],'TZ':'UTC','SECURITY_URL_ALLOWLIST_ALLOW_INSECURE_HTTP':'false','SECURITY_URL_ALLOWLIST_ALLOW_PRIVATE_HOSTS':'false'}
    with (R/'gateway.log').open('ab') as log:
        process=subprocess.Popen([str(binary)],env=env,cwd=R,stdout=log,stderr=log,start_new_session=True)
    (R/'gateway.pid').write_text(str(process.pid))
    for _ in range(60):
        if process.poll() is not None: raise SystemExit('Gateway stopped: inspect private .runtime/gateway.log')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8180/health',timeout=1) as response:
                if response.status==200:
                    print('Pilot ready: http://127.0.0.1:8180; credentials in .runtime/local.json'); return
        except OSError: pass
        time.sleep(1)
    raise SystemExit('Gateway not ready; inspect private logs')

def stop():
    # Redis authenticated shutdown and pg_ctl use this instance's own paths/port.
    pidfile=R/'gateway.pid'
    if pidfile.exists():
        pid=int(pidfile.read_text())
        desc=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
        if str(R/'sub2api') in desc:
            os.kill(pid,signal.SIGTERM)
        pidfile.unlink()
    if (R/'local.json').exists():
        cfg=json.loads((R/'local.json').read_text())
        subprocess.run([str(REDIS/'redis-cli'),'-h','127.0.0.1','-p',str(PORTS[2]),'shutdown'],env={**os.environ,'REDISCLI_AUTH':cfg['redis_password']},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if (R/'postgres'/'postmaster.pid').exists():
        run([PG/'pg_ctl','-D',R/'postgres','stop','-m','fast'])
    print('Stopped local pilot; data retained')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','stop']);a=p.parse_args()
    if a.action=='start': start(R/'sub2api')
    else: stop()
