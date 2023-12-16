"""Serves the display page with caching turned off.

python3 display_server.py <port> <folder>
"""
import functools
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def main():
    port, folder = int(sys.argv[1]), sys.argv[2]
    handler = functools.partial(NoCacheHandler, directory=folder)
    ThreadingHTTPServer(('', port), handler).serve_forever()


if __name__ == '__main__':
    main()
