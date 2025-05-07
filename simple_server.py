#!/usr/bin/env python3
"""
Simple HTTP server for testing.
"""
import http.server
import socketserver

PORT = 8000

handler = http.server.SimpleHTTPRequestHandler
httpd = socketserver.TCPServer(("", PORT), handler)

print(f"Serving at http://localhost:{PORT}")
httpd.serve_forever()