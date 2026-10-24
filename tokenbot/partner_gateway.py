"""Trial API and private usage portal; bind loopback behind verified HTTPS."""
import asyncio
import hmac
import hashlib
import json
import io
import os
import time
import logging
from contextlib import asynccontextmanager, ExitStack
from pathlib import Path

import httpx
import zstandard
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from tokenbot.partner_portal import ClientRegistry, install_portal
from tokenbot.model_catalog import discovery, validate_selection
from tokenbot.customer_billing import BillingError, account_lock
from tokenbot.pricing_policy import pricing_lock
from tokenbot.gateway_events import record_failure

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'gpt-6.1-sol'


def create_app(config, transport=None):
    concurrency = int(config.get('max_concurrency', 1))
    if concurrency < 1 or concurrency > 8:
        raise ValueError('Invalid bridge concurrency')
    lock = asyncio.Semaphore(concurrency)
    max_pending = int(config.get('max_pending', 4))
    queue_timeout = float(config.get('queue_timeout_seconds', 30))
    if not 0 <= max_pending <= 16 or not 0 < queue_timeout <= 60:
        raise ValueError('Invalid bridge queue limits')
    registry = ClientRegistry(config)
    client = httpx.AsyncClient(base_url='http://127.0.0.1:8180', trust_env=False,
                              follow_redirects=False, timeout=300, transport=transport)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await client.aclose()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    if config.get("public_origin"):
        install_portal(app, config, registry)
    app.state.pool_state = registry.default
    app.state.client_registry = registry

    def error(message, status, headers=None):
        return JSONResponse({'error': {'message': message, 'type': 'partner_test'}}, status_code=status, headers=headers)

    @app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
    async def proxy(path: str, request: Request):
        if request.client is None or request.client.host not in config['allowed_ips']:
            return error('Device not allowed', 403)
        auth = request.headers.get('authorization', '')
        if (config['expires_at'] is not None and time.time() >= config['expires_at'] and
                hmac.compare_digest(auth.encode(), ('Bearer '+config['key']).encode())):
            return error('Test expired', 403)
        found = registry.resolve(key=auth[7:]) if auth.startswith('Bearer ') else None
        if not auth:
            found = app.state.portal_identity(request) if config.get('public_origin') else None
            if found and request.method != 'GET' and not app.state.portal_same_origin(request):
                return error('Invalid request origin', 403)
        if not found:
            return error('Invalid, disabled or expired access key', 401)
        client_id, state = found
        started = time.monotonic()
        model = None
        def failed(message, status, code, headers=None, not_forwarded=True):
            rid = record_failure(state.config, model, status, code, time.monotonic()-started, not_forwarded)
            return error(message, status, {**(headers or {}), 'X-Request-ID': rid,
                         'X-TokenBot-Error-Source': code})
        if state.config.get('billing', {}).get('status') == 'activating':
            return failed('Billing activation is in progress; retry later', 409, 'billing_activation')
        if (request.query_params and not (request.method == 'GET' and path == 'v1/models'
                and set(request.query_params) == {'client_version'})) or (request.method, path) not in {
                ('GET', 'v1/models'), ('POST', 'v1/responses'), ('POST', 'v1/chat/completions')}:
            return error('Endpoint not available in this test', 404)
        body = b''
        if request.method == 'POST':
            try:
                async with asyncio.timeout(10):
                    async for chunk in request.stream():
                        body += chunk
                        if len(body) > 2 * 1024 * 1024:
                            return error('Test input exceeds 2 MiB', 413)
                encoding = request.headers.get('content-encoding', 'identity').lower()
                if encoding == 'zstd':
                    with zstandard.ZstdDecompressor(max_window_size=8192).stream_reader(io.BytesIO(body)) as reader:
                        body = reader.read(2 * 1024 * 1024 + 1)
                    if len(body) > 2 * 1024 * 1024:
                        return error('Decompressed input exceeds 2 MiB', 413)
                elif encoding != 'identity':
                    return error('Unsupported request encoding', 415)
                data = json.loads(body)
                selection_error = validate_selection(data)
                if selection_error:
                    return error(selection_error, 400)
                model = data.get('model')
                if data.get('background') or data.get('service_tier') not in (None, 'auto', 'default'):
                    return error('Background and priority requests are disabled', 400)
            except (ValueError, UnicodeError, TimeoutError, zstandard.ZstdError):
                return error('Invalid request', 400)
        if request.method == 'GET':
            return discovery()
        queue_start = time.monotonic()
        if lock.locked():
            busy_headers = {'Retry-After': '5', 'X-TokenBot-Error-Source': 'bridge_capacity'}
            if sum(s.pending for s in registry.states.values()) >= max_pending:
                return failed('Server queue is full; subscription quota was not checked or consumed', 503, 'bridge_capacity', busy_headers)
            state.pending += 1
            try:
                while True:
                    remaining = queue_timeout - (time.monotonic() - queue_start)
                    if remaining <= 0:
                        return failed('Server queue wait timed out; retry later', 503, 'bridge_capacity', busy_headers)
                    if await request.is_disconnected():
                        return error('Client disconnected before model execution', 499)
                    try:
                        await asyncio.wait_for(lock.acquire(), min(.25, remaining))
                        break
                    except TimeoutError:
                        continue
            finally:
                state.pending -= 1
        else:
            await lock.acquire()
        queue_start_acquired = time.monotonic()
        current = registry.resolve(key=auth[7:]) if auth else app.state.portal_identity(request)
        if current is None or current[1] is not state:
            lock.release()
            return error('Access disabled while waiting', 401)
        billing_guard = ExitStack()
        try:
            if config.get('clients_path'):
                billing_guard.enter_context(pricing_lock(config['clients_path']))
                policy = json.loads(Path(config['clients_path']).read_text())
                if (policy.get('billing_live') and client_id.startswith('web-') and
                        state.config.get('billing', {}).get('status') != 'active' and
                        state.config.get('free_test_authorized') is not True):
                    billing_guard.close()
                    lock.release()
                    return failed('Account billing must be activated before calling models', 403, 'billing_not_active')
            if client_id.startswith('web-') and state.config.get('selection_path'):
                billing_guard.enter_context(account_lock(state.config))
                # Activation may have completed while this request was queued.
                checked = registry.resolve(key=auth[7:]) if auth else app.state.portal_identity(request)
                if checked is None or checked[1] is not state:
                    billing_guard.close()
                    lock.release()
                    return error('Account configuration changed; retry later', 409)
        except (BillingError, OSError, ValueError) as exc:
            billing_guard.close()
            lock.release()
            logging.getLogger(__name__).warning('billing_guard_failed type=%s errno=%s', type(exc).__name__, getattr(exc, 'errno', None))
            return failed(exc.message, exc.status, 'billing_guard') if isinstance(exc, BillingError) else failed('Billing guard unavailable; retry later', 503, 'billing_guard')
        state.active += 1
        selected = state.selected
        upstream_key = state.pools[selected]["key"]
        released = False
        def release():
            nonlocal released
            if not released:
                released = True
                billing_guard.close()
                lock.release()
                state.active -= 1
        try:
            # Preserve conversation affinity without forwarding cookies or arbitrary auth headers.
            request_headers = {name: request.headers[name] for name in (
                'session_id', 'conversation_id', 'x-codex-turn-state', 'x-codex-turn-metadata',
                'originator', 'openai-beta', 'x-client-request-id') if name in request.headers}
            if client_id != 'partner':
                for name in ('session_id', 'conversation_id'):
                    if name in request_headers:
                        request_headers[name] = hashlib.sha256((client_id+':'+request_headers[name]).encode()).hexdigest()
            request_headers.update({'Authorization': 'Bearer ' + upstream_key, 'Content-Type': 'application/json'})
            upstream = await client.send(client.build_request('POST', '/' + path, content=body,
                headers=request_headers), stream=True)
            if 300 <= upstream.status_code < 400:
                await upstream.aclose()
                release()
                return error('Unexpected upstream redirect', 502)
        except asyncio.CancelledError:
            release()
            raise
        except Exception:
            release()
            return failed('Local gateway unavailable; request was not retried', 502, 'gateway_transport', not_forwarded=False)

        async def cleanup():
            try:
                await upstream.aclose()
            finally:
                release()

        async def chunks():
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await cleanup()

        response_headers = {name: value for name, value in upstream.headers.items()
                            if name in ('retry-after', 'x-request-id', 'x-codex-turn-state') or name.startswith('x-ratelimit-')}
        response_headers.update({'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no', 'X-TokenBot-Pool': selected,
                                 'X-TokenBot-Queue-Wait-Ms': str(round((queue_start_acquired-queue_start)*1000))})
        if upstream.status_code >= 400:
            response_headers['X-TokenBot-Error-Source'] = 'upstream_gateway'
            response_headers['X-TokenBot-Request-ID'] = record_failure(state.config, model, upstream.status_code, 'upstream_gateway', time.monotonic()-started, False)
        return StreamingResponse(chunks(), status_code=upstream.status_code,
                                 media_type=upstream.headers.get('content-type', 'application/json'),
                                 headers=response_headers,
                                 background=BackgroundTask(cleanup))

    return app


def app_factory():
    path = Path(os.environ.get('TOKENBOT_BRIDGE_CONFIG', ROOT / '.runtime/partner-test.json'))
    return create_app(json.loads(path.read_text()))
