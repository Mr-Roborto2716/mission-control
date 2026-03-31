#!/usr/bin/env python3
import http.server, os
PORT = 8766
DIR  = os.path.dirname(os.path.abspath(__file__))
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=DIR, **kw)
    def log_message(self, *a): pass
if __name__ == "__main__":
    with http.server.HTTPServer(("0.0.0.0", PORT), H) as s:
        print(f"Mission Control serving at http://0.0.0.0:{PORT}")
        s.serve_forever()
