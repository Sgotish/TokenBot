"""Loopback-only data source for isolated Windows UI tests. No upstream credentials."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
from datetime import datetime, timezone

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        resets = datetime.fromtimestamp(time.time() + 3600, timezone.utc).isoformat()
        data = {'selected_pool': 'plus', 'snapshot_stale': False, 'active_requests': 0,
                'accounts': [{'label': 'Plus', 'snapshot_stale': False, 'windows': [
                    {'label': '5 小时窗口', 'remaining_percent': 94, 'stale': False, 'resets_at': resets},
                    {'label': '7 天窗口', 'remaining_percent': 97, 'stale': False, 'resets_at': resets},
                ]}], 'records': []}
        body = json.dumps(data).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(body)

    def log_message(self, *_):
        pass

if __name__ == '__main__':
    HTTPServer(('127.0.0.1', 18791), Handler).serve_forever()
