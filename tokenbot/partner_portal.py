"""Private partner controls. Never expose panel credentials or raw account objects."""
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from .gateway_events import recent_failures

STATIC = Path(__file__).with_name('static')
COOKIE = '__Host-tokenbot-session'

def accepts_digest(config, digest):
    return hmac.compare_digest(hashlib.sha256(config['key'].encode()).hexdigest(), digest) or any(
        item.get('enabled') is True and hmac.compare_digest(item.get('digest', ''), digest)
        for item in config.get('aliases', {}).values())


class PortalSecurityHeaders:
    """Add headers without wrapping receive: queued requests must see disconnects."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        values = {
            b'cache-control': b'no-store', b'x-content-type-options': b'nosniff',
            b'referrer-policy': b'no-referrer', b'x-frame-options': b'DENY',
            b'content-security-policy': b"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        }
        async def send_headers(message):
            if message['type'] == 'http.response.start':
                message = {**message, 'headers': [(k,v) for k,v in message.get('headers', []) if k.lower() not in values] + list(values.items())}
            await send(message)
        await self.app(scope, receive, send_headers)


class PoolState:
    def __init__(self, config):
        self.config = config
        self.active = 0
        self.pending = 0
        self.pools = config.get('pools', {'auto': {'key': config['key'], 'label': '双订阅自动'}})
        self.path = Path(config['selection_path']) if config.get('selection_path') else None
        self.selected = 'auto'
        if self.path and self.path.exists():
            self.selected = json.loads(self.path.read_text())['selected_pool']
        if self.selected not in self.pools:
            raise ValueError('Saved pool is unavailable')

    def select(self, pool):
        if pool not in self.pools:
            raise ValueError('Unknown pool')
        if self.active or self.pending:
            raise RuntimeError('Requests are in progress')
        if self.path:
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'selected_pool': pool}))
            tmp.chmod(0o600)
            tmp.replace(self.path)
        self.selected = pool

    def status(self):
        try:
            failures, failures_unavailable = recent_failures(self.config), False
        except (OSError, ValueError):
            failures, failures_unavailable = [], True
        try:
            snapshot = json.loads(Path(self.config['snapshot_path']).read_text())
        except (OSError, ValueError, KeyError):
            snapshot = {'generated_at': None, 'accounts': [], 'records': [], 'totals': {}, 'error': '用量数据暂不可用'}
        return {**snapshot, 'snapshot_stale': not snapshot.get('generated_at') or time.time()-snapshot['generated_at'] > 180,
                'recent_failures': failures, 'failures_unavailable': failures_unavailable,
                'selected_pool': self.selected, 'active_requests': self.active, 'queued_requests': self.pending,
                'pools': [{'id': k, 'label': v['label']} for k, v in self.pools.items()],
                'platform_quota': None, 'expires_at': self.config['expires_at'],
                'model': 'gpt-6.1-sol'}


class ClientRegistry:
    """Independent customer routing and usage; a missing/broken registry fails closed."""
    def __init__(self, config):
        self.config = config
        self.default = PoolState(config)
        self.states = {'partner': self.default}

    def entries(self):
        entries = {'partner': self.config}
        if self.config.get('clients_path'):
            data = json.loads(Path(self.config['clients_path']).read_text())
            for ident, cfg in data['clients'].items():
                if ident == 'partner' or not ident or not isinstance(cfg, dict):
                    raise ValueError('Invalid customer registry')
                entries[ident] = cfg
        # A shared selection or usage file would defeat customer isolation.
        for field in ('key', 'selection_path', 'snapshot_path'):
            values = [x[field] for x in entries.values() if field in x]
            if len(values) != len(set(values)):
                raise ValueError('Duplicate customer configuration')
        owned_keys = set()
        public_digests = set()
        for cfg in entries.values():
            digests = [hashlib.sha256(cfg['key'].encode()).hexdigest(),
                       *[v['digest'] for v in cfg.get('aliases', {}).values()]]
            if len(digests) != len(set(digests)) or public_digests.intersection(digests):
                raise ValueError('Customer credentials must be distinct')
            public_digests.update(digests)
            keys = {p['key'] for p in cfg.get('pools', {}).values()}
            if owned_keys & keys:
                raise ValueError('Customers must have separate upstream keys')
            owned_keys.update(keys)
        return entries

    def resolve(self, *, key=None, ident=None):
        try:
            entries = self.entries()
            for cid, cfg in entries.items():
                if ((ident is not None and ident != cid) or
                        (key is not None and not accepts_digest(cfg, hashlib.sha256(key.encode()).hexdigest()))):
                    continue
                if key is None and ident is None:
                    return None
                if cfg.get('enabled', True) is not True or (cfg.get('expires_at') is not None and time.time() >= cfg['expires_at']):
                    return None
                state = self.states.get(cid)
                if state is None:
                    state = self.states[cid] = PoolState(cfg)
                elif state.config != cfg:
                    if state.active or state.pending:
                        return None
                    state = self.states[cid] = PoolState(cfg)
                return cid, state
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None
        return None


def install_portal(app, config, registry):
    sessions = {}
    failures = []
    origins = {config['public_origin'].rstrip('/'), *config.get('allowed_origins', [])}
    for origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('Portal origins must be exact HTTPS origins')

    def same_origin(request):
        return request.headers.get('origin') in origins

    def identity(request):
        auth = request.headers.get('authorization', '')
        if auth:
            return registry.resolve(key=auth[7:]) if auth.startswith('Bearer ') else None
        value = request.cookies.get(COOKIE, '')
        session = sessions.get(hashlib.sha256(value.encode()).hexdigest())
        if session and session['expires'] > time.time():
            found = registry.resolve(ident=session['client'])
            if found and accepts_digest(found[1].config, session['key_hash']):
                return found
        return None

    app.state.portal_identity = identity
    app.state.portal_authorized = lambda request: identity(request) is not None
    app.state.portal_same_origin = same_origin

    app.add_middleware(PortalSecurityHeaders)

    @app.get('/portal')
    async def page():
        return FileResponse(STATIC/'partner.html')

    @app.get('/portal/assets/{name}')
    async def asset(name: str):
        if name not in ('partner.js', 'partner.css'):
            return JSONResponse({'error': 'Not found'}, status_code=404)
        return FileResponse(STATIC/name)

    async def bounded_body(request, limit):
        body = b''
        async for chunk in request.stream():
            body += chunk
            if len(body) > limit:
                raise ValueError('Input too large')
        return body

    @app.post('/portal/api/login')
    async def login(request: Request):
        if not same_origin(request):
            return JSONResponse({'error': '来源不匹配'}, status_code=403)
        now = time.time()
        failures[:] = [t for t in failures if t > now-60]
        if len(failures) >= 20:
            return JSONResponse({'error': '尝试过多，请一分钟后重试'}, status_code=429)
        try:
            raw = await bounded_body(request, 1024)
        except ValueError:
            return JSONResponse({'error': '输入过长'}, status_code=413)
        try:
            key = json.loads(raw).get('key', '')
        except (ValueError, AttributeError):
            key = ''
        found = registry.resolve(key=key) if isinstance(key, str) else None
        if not found:
            failures.append(now)
            return JSONResponse({'error': '接入 Key 不正确'}, status_code=401)
        for k in list(sessions):
            if sessions[k]['expires'] <= now:
                del sessions[k]
        if len(sessions) >= 64:
            sessions.pop(next(iter(sessions)))
        value = secrets.token_urlsafe(32)
        sessions[hashlib.sha256(value.encode()).hexdigest()] = {'expires':now+43200,'client':found[0],
            'key_hash':hashlib.sha256(key.encode()).hexdigest()}
        result = JSONResponse({'ok': True})
        result.set_cookie(COOKIE, value, max_age=43200, secure=True, httponly=True, samesite='strict', path='/')
        return result

    @app.post('/portal/api/logout')
    async def logout(request: Request):
        if not same_origin(request):
            return JSONResponse({'error': '来源不匹配'}, status_code=403)
        sessions.pop(hashlib.sha256(request.cookies.get(COOKIE, '').encode()).hexdigest(), None)
        result = JSONResponse({'ok': True})
        result.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='strict')
        return result

    @app.get('/portal/api/status')
    @app.get('/v1/usage')
    async def status(request: Request):
        found = identity(request)
        if not found:
            return JSONResponse({'error': '请使用自己的接入 Key 登录'}, status_code=401)
        return {**found[1].status(), 'client_label':found[1].config.get('label', 'TokenBots Partner Test')}

    @app.post('/portal/api/pool')
    async def choose(request: Request):
        found = identity(request)
        if not found or not same_origin(request):
            return JSONResponse({'error': '请重新登录'}, status_code=403)
        state = found[1]
        try:
            raw = await bounded_body(request, 256)
        except ValueError:
            return JSONResponse({'error': '输入过长'}, status_code=413)
        try:
            state.select(json.loads(raw)['pool'])
        except RuntimeError:
            return JSONResponse({'error': '仍有调用进行中，请结束当前任务后再切换'}, status_code=409)
        except (ValueError, KeyError, TypeError):
            return JSONResponse({'error': '无效号池'}, status_code=400)
        except OSError:
            return JSONResponse({'error': '选择未能保存，请稍后重试'}, status_code=503)
        return {'selected_pool': state.selected}
