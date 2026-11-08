"""Actual native app-server, four disposable projects, no model/API requests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import sqlite3
import subprocess
import threading
import uuid

a = argparse.ArgumentParser()
a.add_argument('--app', required=True)
a.add_argument('--home', required=True)
args = a.parse_args()
app, home = Path(args.app), Path(args.home)
# Only CI's explicit fixture profile may be modified by the index fault injection.
key = json.loads((app/'resources/tokenbots-native.json').read_text(encoding='utf-8-sig'))['key']
assert key == 'fixture-only-not-a-real-key'
assert home.name == hashlib.sha256(key.encode()).hexdigest()[:16]
rollouts = home/'sessions/2026/11/08'
rollouts.mkdir(parents=True, exist_ok=True)
ids, paths = [], []
for n in range(4):
    uid = str(uuid.uuid4()); ids.append(uid)
    project = home/f'synthetic-project-{n}'; project.mkdir(exist_ok=True)
    records = [
        {'timestamp':'2026-11-08T12:00:00Z', 'type':'session_meta', 'payload':{
            'id':uid, 'timestamp':'2026-11-08T12:00:00Z', 'cwd':str(project),
            'originator':'codex_cli_rs', 'cli_version':'0.0.0', 'source':'cli', 'model_provider':'openai'}},
        {'timestamp':'2026-11-08T12:00:01Z', 'type':'event_msg', 'payload':{
            'type':'user_message', 'message':'Synthetic history fixture', 'images':[]}},
    ]
    file = rollouts/f'rollout-2026-11-08T12-00-00-{uid}.jsonl'
    file.write_text(''.join(json.dumps(r)+'\n' for r in records), encoding='utf8'); paths.append(file)
before = [hashlib.sha256(f.read_bytes()).hexdigest() for f in paths]
env = {**os.environ, 'CODEX_HOME':str(home)}
p = subprocess.Popen([str(app/'resources/codex.exe'), 'app-server', '--stdio'],
    env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    text=True, encoding='utf8', bufsize=1)
responses = queue.Queue()
def read():
    for line in p.stdout:
        responses.put(json.loads(line))
threading.Thread(target=read, daemon=True).start()
seq = 0
def request(method, params):
    global seq
    seq += 1
    p.stdin.write(json.dumps({'id':seq,'method':method,'params':params})+'\n'); p.stdin.flush()
    while True:
        result = responses.get(timeout=25)
        if result.get('id') == seq:
            assert 'error' not in result, result.get('error')
            return result['result']
def listed(scan=False):
    result = request('thread/list', {'limit':100,'archived':False,'modelProviders':[],
        'sourceKinds':['cli','vscode','appServer'],'useStateDbOnly':not scan})
    return len(set(ids) & {t['id'] for t in result['data']})
try:
    request('initialize', {'clientInfo':{'name':'tokenbots_history_fixture','version':'1'},'capabilities':{'experimentalApi':True}})
    p.stdin.write('{"method":"initialized"}\n'); p.stdin.flush()
    assert listed(True) == 4
    db = next(home.glob('state_*.sqlite'))
    with sqlite3.connect(db) as conn:
        conn.execute('DELETE FROM threads WHERE id=?', (ids[0],))
    assert listed() == 3
    node = app/'resources/cua_node/bin/node.exe'
    subprocess.run([str(node), str(app/'history-repair.cjs'), str(app)], env=env, check=True, timeout=30)
    assert listed() == 4
    assert [hashlib.sha256(f.read_bytes()).hexdigest() for f in paths] == before
    result = json.loads((home/'tokenbots-history-check.json').read_text())
    assert result['status'] == 'completed'
    print('PASS: four projects -> missing index shows three -> startup repair restores four; rollouts unchanged; no inference')
finally:
    p.terminate()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill()
