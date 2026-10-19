"""Read-only operator dashboard, isolated from customer and control-plane keys."""
import hmac
import json
import os
from pathlib import Path
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

STATIC = Path(__file__).parent/'static'


def create_app(state, secret):
    if len(secret) < 40:
        raise ValueError('Research access secret must have at least 40 characters')
    state = Path(state)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
        return response

    @app.get('/research')
    @app.get('/research/')
    def index():
        return FileResponse(STATIC/'research.html')

    @app.get('/research/assets/{name}')
    def asset(name):
        if name not in ('research.js', 'research.css'):
            return JSONResponse({'error': 'not found'}, status_code=404)
        return FileResponse(STATIC/name)

    @app.get('/research/api/report')
    def get_report(request: Request):
        supplied = request.headers.get('authorization', '')
        if not hmac.compare_digest(supplied.encode(), ('Bearer '+secret).encode()):
            return JSONResponse({'error': '研究页访问密钥无效'}, status_code=401)
        try:
            data = json.loads((state/'report.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return JSONResponse({'error': '等待首次研究采集'}, status_code=503)
        data['report_stale'] = time.time()-data.get('generated_at', 0) > 900
        return data

    return app


def app_factory():
    state = Path(os.environ.get('TOKENBOT_RESEARCH_STATE', '/var/lib/tokenbot-research'))
    return create_app(state, (state/'access.secret').read_text(encoding='utf-8').strip())
