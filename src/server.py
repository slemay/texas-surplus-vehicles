#!/usr/bin/env python3
"""
Texas Surplus Vehicles - Local Web Application Server
Serves static frontend assets from public/, data assets from public/data/,
and handles POST /api/refresh for live inventory synchronization.
"""

import http.server
import socketserver
import json
import os
import sys

# Ensure src module directory is in sys.path
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SRC_DIR, '..'))
PUBLIC_DIR = os.path.join(PROJECT_ROOT, 'public')

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from refresh_inventory import run_refresh

PORT = 8080

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def do_GET(self):
        # Route alias mapping for backward compatibility
        path = self.path.split('?')[0]
        
        if path in ['/vehicles_final.json', '/data/vehicles_final.json']:
            target_path = os.path.join(PUBLIC_DIR, 'data', 'vehicles_final.json')
            if not os.path.exists(target_path):
                target_path = os.path.join(PROJECT_ROOT, 'data', 'vehicles_final.json')
            return self._serve_custom_file(target_path, 'application/json')
            
        elif path in ['/Texas_State_Surplus_Vehicles.pdf', '/data/Texas_State_Surplus_Vehicles.pdf']:
            target_path = os.path.join(PUBLIC_DIR, 'data', 'Texas_State_Surplus_Vehicles.pdf')
            if not os.path.exists(target_path):
                target_path = os.path.join(PROJECT_ROOT, 'data', 'Texas_State_Surplus_Vehicles.pdf')
            return self._serve_custom_file(target_path, 'application/pdf')

        elif path.startswith('/images/'):
            rel_img = path.lstrip('/')
            target_img = os.path.join(PUBLIC_DIR, rel_img)
            if os.path.exists(target_img):
                content_type = 'image/svg+xml' if target_img.endswith('.svg') else 'image/jpeg'
                return self._serve_custom_file(target_img, content_type)

        super().do_GET()

    def _serve_custom_file(self, filepath, content_type):
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def do_POST(self):
        if self.path == '/api/refresh':
            try:
                print("\n[API] Received live refresh request from web dashboard...")
                run_refresh()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = json.dumps({"status": "success", "message": "Inventory refreshed successfully!"})
                self.wfile.write(response.encode('utf-8'))
            except Exception as e:
                print(f"[API Error] Failed to refresh inventory: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({"status": "error", "message": str(e)})
                self.wfile.write(response.encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def main():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"[*] Dashboard Web Server running on http://localhost:{PORT}")
        print(f"    Serving frontend from: {PUBLIC_DIR}")
        httpd.serve_forever()

if __name__ == '__main__':
    main()
