#!/usr/bin/env python3
"""Run the temporary loopback gateway; stop its specific Funnel at key expiry."""
import json
import subprocess
import signal
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
cfg=json.loads((ROOT/'.runtime/partner-test.json').read_text())
child=subprocess.Popen([sys.executable,'-m','uvicorn','tokenbot.partner_gateway:app_factory',
    '--factory','--host','127.0.0.1','--port','8181','--no-proxy-headers','--no-access-log',
    '--limit-concurrency','16'],cwd=ROOT)
def stop(signum, frame):
    raise SystemExit(0)
signal.signal(signal.SIGTERM,stop)
signal.signal(signal.SIGINT,stop)
try:
    while time.time()<cfg['expires_at'] and child.poll() is None:
        time.sleep(min(20,max(0,cfg['expires_at']-time.time())))
finally:
    if child.poll() is None:
        child.terminate()
        try: child.wait(timeout=15)
        except subprocess.TimeoutExpired: child.kill();child.wait()
    # Do not touch unrelated Serve endpoints or a replacement configuration.
    try:
        result=subprocess.run(['tailscale','funnel','status','--json'],capture_output=True,text=True,check=True)
        state=json.loads(result.stdout)
        targets=[v for k,v in state.get('Web',{}).items() if k.endswith(':443')]
        if any(t.get('Handlers',{}).get('/',{}).get('Proxy')=='http://127.0.0.1:8181' for t in targets):
            subprocess.run(['tailscale','funnel','--https=443','off'],capture_output=True,check=True)
    except Exception:
        print('Review Funnel port 443 cleanup manually.',flush=True)
