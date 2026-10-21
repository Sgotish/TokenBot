"""Bounded Windows API/CLI qualification; synthetic prompts, isolated home, fail-stop."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


def api_once(access_path, number):
    """Same short Responses probe as the earlier soak, without a CLI's large system prompt."""
    access = json.loads(Path(access_path).read_text(encoding='utf-8-sig'))
    body = {'model':'gpt-6.1-sol','stream':True,'store':False,'reasoning':{'effort':'low'},
            'input':[{'role':'user','content':[{'type':'input_text','text':f'What is {number}+7? Reply only the integer.'}]}]}
    url = access.get('base_url', access.get('url', ''))
    req = urllib.request.Request(url.rstrip('/')+'/responses', data=json.dumps(body).encode(),
                                 headers={'Authorization':'Bearer '+access['key'],'Content-Type':'application/json'})
    text = ''; done = None; start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            for line in response:
                if time.time()-start > 110: raise TimeoutError()
                if not line.startswith(b'data:'): continue
                raw = line[5:].strip()
                if raw == b'[DONE]': continue
                event = json.loads(raw)
                if event.get('type') == 'response.output_text.delta': text += event.get('delta','')
                if event.get('type') == 'response.completed': done = event.get('response',{})
                if event.get('type') in ('error','response.failed','response.incomplete'): raise RuntimeError('stream_error')
        print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':text}}))
        if not done or done.get('status') != 'completed': raise RuntimeError('missing_completion')
        print(json.dumps({'type':'turn.completed','usage':done.get('usage',{})}))
        return 0
    except Exception as e:
        print(json.dumps({'type':'error','error_type':type(e).__name__}))
        return 1


def assess(events, expected, returncode):
    messages = [e['item'].get('text', '') for e in events
                if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'agent_message']
    done = [e for e in events if e.get('type') == 'turn.completed']
    errors = [e for e in events if e.get('type') in ('error', 'turn.failed')]
    return {'pass': returncode == 0 and len(done) == 1 and messages == [expected] and not errors,
            'answer': '\n'.join(messages), 'completed': len(done) == 1,
            'errors': [e.get('type') for e in errors], 'usage': done[-1].get('usage', {}) if done else {}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--home', type=Path, required=True)
    p.add_argument('--hours', type=float, default=24)
    p.add_argument('--interval', type=int, default=900)
    p.add_argument('--transport', choices=('api','cli'), default='api')
    p.add_argument('--name', default='soak-24h')
    a = p.parse_args()
    if os.name != 'nt' or not 0 < a.hours <= 24 or not 60 <= a.interval <= 900:
        p.error('Windows only; duration 0–24h and interval 60–900 seconds')
    report = a.root / 'reports' / a.name
    report.mkdir(parents=True, exist_ok=False)  # refuses restarts or duplicate consumption
    work = a.root / 'work'
    work.mkdir(exist_ok=True)
    started = time.time()
    deadline = started + a.hours * 3600
    config = a.home / 'config.toml'
    before = hashlib.sha256(config.read_bytes()).hexdigest()
    state = {'state': 'running', 'pid': os.getpid(), 'started_at': started, 'deadline': deadline,
             'model': 'gpt-6.1-sol', 'reasoning': 'low', 'interval_s': a.interval,
             'transport': a.transport,
             'requests': 0, 'passed': 0, 'usage': {}, 'elapsed_s': 0}
    def status():
        state['checked_at'] = time.time()
        state['elapsed_s'] = round(time.time() - started, 3)
        tmp = report / 'status.tmp'
        tmp.write_text(json.dumps(state, indent=2), encoding='utf-8')
        tmp.replace(report / 'status.json')
    def record(row):
        with (report / 'results.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
            f.flush()
            os.fsync(f.fileno())
    status()
    # Keep only this process awake; no permanent power-plan change.
    if not ctypes.windll.kernel32.SetThreadExecutionState(0x80000001):
        state['state'] = 'failed'; state['error'] = 'cannot_inhibit_sleep'; status(); return 1
    last_tick = started
    try:
        next_call = started
        while True:
            now = time.time()
            if now - last_tick > 90:
                raise RuntimeError('machine_suspended_or_scheduler_gap')
            last_tick = now
            if (report / 'STOP').exists():
                state['state'] = 'stopped'; break
            if now < next_call:
                status(); time.sleep(min(30, next_call-now)); continue
            i = state['requests'] + 1
            prompt = f'What is {i}+7? Reply only the integer. Do not use tools.'
            cmd = ['node', str(a.root / 'TokenBots' / 'tokenbots.cjs'), 'run', '--home', str(a.home),
                   '--', 'exec', '--skip-git-repo-check', '--ephemeral', '--sandbox', 'read-only',
                   '--json', '-m', 'gpt-6.1-sol', '-c', 'model_reasoning_effort="low"', prompt]
            if a.transport == 'api':
                cmd = [sys.executable, str(Path(__file__).resolve()), '--api-once',
                       str(a.root / 'TokenBots' / 'access.json'), str(i)]
            call_start = time.time()
            proc = subprocess.Popen(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                out, err = proc.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
                proc.communicate(timeout=15)
                raise RuntimeError('cli_timeout')
            events = []
            for line in out.decode('utf-8', errors='replace').splitlines():
                try: events.append(json.loads(line))
                except ValueError: pass
            row = {'request': i, 'started_at': call_start, 'elapsed_s': round(time.time()-call_start, 3),
                   'returncode': proc.returncode, **assess(events, str(i+7), proc.returncode)}
            # Only synthetic agent messages and completion metadata are persisted.
            row['events'] = [e for e in events if e.get('type') in ('thread.started', 'turn.started', 'turn.completed')]
            record(row)
            state['requests'] = i
            if row['pass']: state['passed'] += 1
            for key, value in row['usage'].items():
                if isinstance(value, int): state['usage'][key] = state['usage'].get(key, 0) + value
            state['last_result'] = {k:v for k,v in row.items() if k != 'events'}
            if not row['pass']:
                state['state'] = 'failed'; break
            if call_start >= deadline:
                state['state'] = 'passed'; break
            next_call = min(deadline, call_start + a.interval)
            last_tick = time.time()
            status()
    except BaseException as e:
        state['state'] = 'failed'; state['error'] = str(e) if isinstance(e, RuntimeError) else type(e).__name__
    finally:
        state['finished_at'] = time.time()
        state['config_unchanged'] = hashlib.sha256(config.read_bytes()).hexdigest() == before
        if not state['config_unchanged']: state['state'] = 'failed'
        status()
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    return 0 if state['state'] == 'passed' else 1


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--api-once':
        raise SystemExit(api_once(sys.argv[2], int(sys.argv[3])))
    raise SystemExit(main())
