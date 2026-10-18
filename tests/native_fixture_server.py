"""Loopback-only data source for isolated Windows UI tests. No upstream credentials."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
from datetime import datetime, timezone
from pathlib import Path

class Handler(BaseHTTPRequestHandler):
    selected_pool = "plus"
    pro_reads = 0
    def do_GET(self):
        if self.path.startswith('/v1/models'):
            models=json.loads(Path('integrations/model-catalog/models.json').read_text())['models']
            body=json.dumps({'object':'list','data':[{'id':m['id'],'object':'model','owned_by':'fixture'} for m in models]}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body);return
        if self.path == '/v1/usage' and Handler.selected_pool == 'pro':
            Handler.pro_reads += 1
        resets = datetime.fromtimestamp(time.time() + 3600, timezone.utc).isoformat()
        data = {'selected_pool': Handler.selected_pool, 'snapshot_stale': False, 'active_requests': 0,
                'accounts': [{'label': 'Plus · 账号 2', 'snapshot_stale': False, 'windows': [
                    {'label': '5 小时窗口', 'remaining_percent': 94, 'stale': False, 'resets_at': resets},
                    {'label': '7 天窗口', 'remaining_percent': 97, 'stale': False, 'resets_at': resets},
                ]}, {'label': 'Pro · 账号 1', 'snapshot_stale': False, 'windows': [
                    {'label': '5 小时窗口', 'remaining_percent': 81 if Handler.pro_reads <= 1 else 80, 'stale': False, 'resets_at': resets},
                    {'label': '7 天窗口', 'remaining_percent': 90, 'stale': False, 'resets_at': resets},
                ]}], 'records': []}
        body = json.dumps(data).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        if self.path != '/portal/api/pool' or data.get('pool') not in ('auto', 'plus', 'pro'):
            self.send_error(400)
            return
        Handler.selected_pool = data['pool']
        self.do_GET()

    def log_message(self, *_):
        pass

if __name__ == '__main__':
    HTTPServer(('127.0.0.1', 18791), Handler).serve_forever()
