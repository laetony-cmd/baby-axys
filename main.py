"""
Test minimal - juste un serveur HTTP
"""
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "msg": "Server alive!"}).encode())
    
    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}")

def main():
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting minimal server on port {port}")
    server = HTTPServer(('0.0.0.0', port), TestHandler)
    server.serve_forever()

if __name__ == "__main__":
    main()
