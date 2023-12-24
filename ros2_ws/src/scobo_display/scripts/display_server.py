"""Serves the display page with caching turned off.

python3 display_server.py <port> <folder>
"""
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


class ThreadingServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main():
    port, folder = int(sys.argv[1]), sys.argv[2]
    os.chdir(folder)
    ThreadingServer(('', port), NoCacheHandler).serve_forever()


if __name__ == '__main__':
    main()
