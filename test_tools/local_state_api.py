"""Read-only controller state on the loopback interface."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

OFFLINE = dict(v=1, connected=False, valid=False, notch=None, reverser=None, buttons=0)

class LocalStateAPI(HTTPServer):
    def __init__(self, port):
        self.snapshot = OFFLINE
        super().__init__(('127.0.0.1', port), StateHandler)
        self.worker = Thread(target=self.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
        self.worker.start()

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(.5)
        return connection, address

    def close(self):
        self.shutdown()
        self.server_close()

class StateHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            self.send_error(403)
            return
        if self.path != '/v1/state':
            self.send_error(404)
            return
        payload = json.dumps(self.server.snapshot).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass
