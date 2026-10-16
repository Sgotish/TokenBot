"""Short-lived, owner-only smoke-test queue. No production model routing changes."""
import asyncio
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from .portal_store import PortalError


def mount_pilot(app, settings):
    jobs = {}
    guard = asyncio.Lock()
    heartbeat = 0.0
    last_run = 0.0

    def enabled():
        try:
            return (len(os.getenv('PILOT_WORKER_TOKEN', '')) >= 40
                    and bool(os.getenv('PILOT_ADMIN_USER_ID'))
                    and time.time() < float(os.getenv('PILOT_EXPIRES_AT', '0')))
        except ValueError:
            return False

    async def owner(request):
        store = request.app.state.portal
        if store is None:
            raise PortalError('请先登录管理员账号。', 401)
        actor = await run_in_threadpool(store.session, request.cookies.get('tb_session', ''))
        if actor['role'] != 'admin' or actor['id'] != os.getenv('PILOT_ADMIN_USER_ID'):
            raise PortalError('此测试仅向指定管理员开放。', 403)
        return actor

    async def body(request):
        if request.headers.get('content-type', '').split(';')[0] != 'application/json':
            raise PortalError('需要 JSON 请求。', 415)
        result = bytearray()
        async with asyncio.timeout(5):
            async for chunk in request.stream():
                result.extend(chunk)
                if len(result) > 8192:
                    raise PortalError('请求过大。', 413)
        value = json.loads(result)
        if not isinstance(value, dict):
            raise ValueError()
        return value

    def expire():
        now = time.time()
        for job in jobs.values():
            if job['status'] in ('queued', 'running') and now - job['created_at'] > 180:
                job.update(status='unknown', output='等待超时；结果未知，不会自动重发。')
        for jid in list(jobs):
            if now - jobs[jid]['created_at'] > 3600:
                del jobs[jid]

    @app.get('/admin/subscription-test')
    async def page(request: Request):
        try:
            await owner(request)
        except PortalError as exc:
            return JSONResponse({'error': exc.message}, status_code=exc.status)
        return FileResponse(Path(__file__).parent / 'static' / 'subscription-test.html')

    @app.api_route('/api/pilot/{action:path}', methods=['GET', 'POST'])
    async def api(action: str, request: Request):
        nonlocal heartbeat, last_run
        try:
            if not enabled():
                raise PortalError('测试入口未启用或已到期。', 503)
            if request.query_params:
                raise PortalError('不接受网址参数。', 400)
            worker = action.startswith('worker/')
            if worker:
                if request.method != 'POST' or not hmac.compare_digest(
                        request.headers.get('authorization', ''),
                        'Bearer ' + os.environ['PILOT_WORKER_TOKEN']):
                    raise PortalError('未授权。', 401)
            else:
                actor = await owner(request)
                if request.method == 'POST':
                    origin = settings.public_origin or str(request.base_url).rstrip('/')
                    if request.headers.get('origin') != origin or request.headers.get('sec-fetch-site') == 'cross-site':
                        raise PortalError('请从本站提交。', 403)
                    if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), actor['csrf']):
                        raise PortalError('验证失败，请重新登录。', 403)
            data = await body(request) if request.method == 'POST' else {}
            async with guard:
                expire()
                if action == 'status' and request.method == 'GET':
                    return {'connected': time.time() - heartbeat < 15,
                            'jobs': list(jobs.values())[-10:], 'model': 'gpt-6.1-sol'}
                if action == 'run' and request.method == 'POST':
                    if set(data) != {'target'} or data['target'] not in ('pro', 'plus'):
                        raise PortalError('仅支持 Pro / Plus 固定短消息测试。', 400)
                    if time.time() - heartbeat >= 15:
                        raise PortalError('本机测试程序未连接。', 503)
                    if time.time() - last_run < 10 or any(j['status'] in ('queued', 'running') for j in jobs.values()):
                        raise PortalError('已有测试或操作太快，请等待。', 429)
                    if len(jobs) >= 20:
                        raise PortalError('本次试验已达请求上限。', 429)
                    jid = secrets.token_hex(16)
                    jobs[jid] = {'id': jid, 'target': data['target'], 'status': 'queued',
                                 'created_at': time.time(), 'model': 'gpt-6.1-sol', 'output': ''}
                    last_run = time.time()
                    return jobs[jid]
                if action == 'worker/claim':
                    heartbeat = time.time()
                    for job in jobs.values():
                        if job['status'] == 'queued':
                            job['status'] = 'running'
                            return {'job': dict(job)}
                    return {'job': None}
                if action == 'worker/result':
                    if set(data) != {'id', 'status', 'output'} or data['status'] not in ('completed', 'failed', 'unknown'):
                        raise ValueError()
                    if not isinstance(data['output'], str) or len(data['output']) > 2000:
                        raise ValueError()
                    job = jobs.get(data['id'])
                    if job is None:
                        raise PortalError('测试不存在或服务已重启。', 404)
                    if job['status'] not in ('running', 'unknown'):
                        raise PortalError('结果已记录。', 409)
                    job.update(status=data['status'], output=data['output'])
                    return {'ok': True}
                raise PortalError('接口不存在。', 404)
        except PortalError as exc:
            return JSONResponse({'error': exc.message}, status_code=exc.status)
        except (ValueError, TypeError, KeyError, TimeoutError, UnicodeError):
            return JSONResponse({'error': '请求无效或超时。'}, status_code=400)
