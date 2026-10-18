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

STATIC = Path(__file__).with_name('static')
COOKIE = '__Host-tokenbot-session'


class PoolState:
    def __init__(self, config):
        self.config = config
        self.active = 0
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
        if self.active:
            raise RuntimeError('Requests are in progress')
        if self.path:
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'selected_pool': pool}))
            tmp.chmod(0o600)
            tmp.replace(self.path)
        self.selected = pool

    def status(self):
        try:
            snapshot = json.loads(Path(self.config['snapshot_path']).read_text())
        except (OSError, ValueError, KeyError):
            snapshot = {'generated_at': None, 'accounts': [], 'records': [], 'totals': {}, 'error': '用量数据暂不可用'}
        return {**snapshot, 'snapshot_stale': not snapshot.get('generated_at') or time.time()-snapshot['generated_at'] > 180,
                'selected_pool': self.selected, 'active_requests': self.active,
                'pools': [{'id': k, 'label': v['label']} for k, v in self.pools.items()],
                'platform_quota': None, 'expires_at': self.config['expires_at'],
                'model': 'gpt-6.1-sol'}


def install_portal(app, config, state):
    sessions = {}
    failures = []
    origins = {config['public_origin'].rstrip('/'), *config.get('allowed_origins', [])}
    for origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('Portal origins must be exact HTTPS origins')

    def same_origin(request):
        return request.headers.get('origin') in origins

    def authorized(request):
        if config['expires_at'] is not None and time.time() >= config['expires_at']:
            return False
        auth = request.headers.get('authorization', '')
        if hmac.compare_digest(auth.encode(), ('Bearer '+config['key']).encode()):
            return True
        value = request.cookies.get(COOKIE, '')
        return sessions.get(hashlib.sha256(value.encode()).hexdigest(), 0) > time.time()

    app.state.portal_authorized = authorized
    app.state.portal_same_origin = same_origin

    @app.middleware('http')
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

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
        if config['expires_at'] is not None and now >= config['expires_at']:
            return JSONResponse({'error': '接入已过期'}, status_code=403)
        try:
            raw = await bounded_body(request, 1024)
        except ValueError:
            return JSONResponse({'error': '输入过长'}, status_code=413)
        try:
            key = json.loads(raw).get('key', '')
        except (ValueError, AttributeError):
            key = ''
        if not isinstance(key, str) or not hmac.compare_digest(key.encode(), config['key'].encode()):
            failures.append(now)
            return JSONResponse({'error': '接入 Key 不正确'}, status_code=401)
        for k in list(sessions):
            if sessions[k] <= now:
                del sessions[k]
        if len(sessions) >= 64:
            sessions.pop(next(iter(sessions)))
        value = secrets.token_urlsafe(32)
        sessions[hashlib.sha256(value.encode()).hexdigest()] = now+43200
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
        if not authorized(request):
            return JSONResponse({'error': '请使用搭档接入 Key 登录'}, status_code=401)
        return state.status()

    @app.post('/portal/api/pool')
    async def choose(request: Request):
        if not authorized(request) or not same_origin(request):
            return JSONResponse({'error': '请重新登录'}, status_code=403)
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
