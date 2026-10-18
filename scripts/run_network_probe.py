#!/usr/bin/env python3
"""Temporary, bounded fixed-question SSE adapter for public network probes.

Never accepts prompts or returns account credentials. Run one worker on loopback,
behind a temporary /network-check/ Caddy route, with a <=15 minute systemd deadline.
"""
import asyncio
import json
import os
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse


def create_app(config, transport=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    cases = {k: dict(v) for k, v in config['cases'].items()}
    if not 0 < config['expires_at'] - time.time() <= 900 or len(cases) > 12:
        raise ValueError('Probe requires a bounded lifetime and at most 12 cases')
    if any(v['mode'] not in ('answer', 'stream') or v.get('uses', 1) != 1 for v in cases.values()):
        raise ValueError('Each fixed probe can be consumed once')
    gate = asyncio.Lock()

    @app.get('/network-check/{capability}')
    async def probe(capability: str, request: Request):
        async with gate:
            case = cases.get(capability)
            if not case or case.get('used') or time.time() >= config['expires_at'] or request.query_params:
                return JSONResponse({'error': 'Probe unavailable'}, status_code=404)
            case['used'] = True  # Budget consumed even on error/disconnect. No automatic replay.
        mode = case['mode']
        prompt = ('What is 17+25? Reply only 42.' if mode == 'answer' else
                  'Write integers 1 through 80, one per line, without skipping. End with END-GD.')
        expected = '42' if mode == 'answer' else '\n'.join(map(str, range(1, 81))) + '\nEND-GD'

        async def output():
            start = time.monotonic()
            text, completed, first_text, delta_count = '', False, None, 0
            usage = {}
            def event(kind, data):
                return 'event: '+kind+'\ndata: '+json.dumps(data, ensure_ascii=False)+'\n\n'
            yield event('probe', {'case':case['label'], 'mode':mode, 'model':'gpt-6.1-sol',
                                  'hold_open_seconds':20 if mode == 'stream' else 0})
            try:
                async with asyncio.timeout(27):
                    async with httpx.AsyncClient(base_url='http://127.0.0.1:8181',
                            transport=transport, trust_env=False, follow_redirects=False,
                            timeout=httpx.Timeout(24, connect=5)) as client:
                        async with client.stream('POST', '/v1/responses', headers={
                            'Authorization':'Bearer '+config['key'], 'Content-Type':'application/json'},
                            json={'model':'gpt-6.1-sol','stream':True,'store':False,
                                  'reasoning':{'effort':'low'}, 'input':[{'role':'user','content':prompt}]}) as response:
                            if response.status_code != 200:
                                yield event('failed', {'http':response.status_code}); return
                            async for line in response.aiter_lines():
                                if not line.startswith('data:'): continue
                                raw=line[5:].strip()
                                if raw=='[DONE]': continue
                                try: item=json.loads(raw)
                                except ValueError: continue
                                kind=item.get('type')
                                if kind=='response.output_text.delta':
                                    delta=item.get('delta',''); text+=delta; delta_count+=1
                                    if len(text)>2000:
                                        yield event('failed',{'error':'output_bound'}); return
                                    if first_text is None: first_text=round(time.monotonic()-start,3)
                                    # Send genuine model text as it arrives; synthetic pacing is only after completion.
                                    yield event('text', {'delta':delta})
                                elif kind=='response.completed':
                                    result=item.get('response',{}); completed=result.get('status')=='completed'
                                    usage={k:v for k,v in result.get('usage',{}).items() if k in ('input_tokens','output_tokens','total_tokens')}
                                elif kind in ('error','response.failed','response.incomplete'):
                                    yield event('failed',{'error':kind}); return
                    model_seconds=round(time.monotonic()-start,3)
                    if mode=='stream':
                        while time.monotonic()-start < 20:
                            if await request.is_disconnected(): return
                            yield ': transport-heartbeat\n\n'
                            await asyncio.sleep(min(2,20-(time.monotonic()-start)))
                    passed=completed and text.strip()==expected
                    yield event('completed', {'pass':passed,'upstream_completed':completed,
                        'first_text_at_server_s':first_text,'model_seconds':model_seconds,
                        'total_seconds':round(time.monotonic()-start,3),'delta_count':delta_count,'usage':usage})
            except asyncio.CancelledError:
                raise
            except Exception as e:
                yield event('failed', {'error':type(e).__name__})
        return StreamingResponse(output(), media_type='text/event-stream',
            headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
    return app


def app_factory():
    return create_app(json.loads(Path(os.environ['TOKENBOT_NETWORK_PROBE_CONFIG']).read_text()))
