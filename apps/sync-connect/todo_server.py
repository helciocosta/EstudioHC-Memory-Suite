import json, os
from http.server import HTTPServer, BaseHTTPRequestHandler

API_BASE = os.getenv('API_BASE', 'https://127.0.0.1:5050')
API_KEY = os.getenv('API_KEY', 'auto')

class TodoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True, 'service': 'todo-sync'}).encode())

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        body['origem'] = 'todo-sync'
        import requests
        try:
            r = requests.post(f'{API_BASE}/api/tarefas', json=body,
                headers={'X-API-Key': API_KEY}, verify=False, timeout=10)
            self.send_response(r.status_code)
        except Exception as e:
            self.send_response(500)
            body = {'error': str(e)}
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

HTTPServer(('0.0.0.0', 5057), TodoHandler).serve_forever()
