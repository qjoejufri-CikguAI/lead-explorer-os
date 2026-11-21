#!/usr/bin/env python3
import subprocess
import sys
import os
import json
import sqlite3
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

SUPABASE_URL = 'https://ypcccthqbnkurkslsvdi.supabase.co'
SUPABASE_KEY = 'sb_publishable_psEsjDPRCqYEencypzNW9g_NgRW7ZPj'
SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': 'Bearer ' + SUPABASE_KEY,
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates',
}

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'leads.db')

# Global hunter process handle
hunter_process = None

class Handler(BaseHTTPRequestHandler):
    def _send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/run':
            query = urllib.parse.parse_qs(parsed.query)
            niche = query.get('niche', [None])[0]
            area = query.get('area', [None])[0]
            if niche and area:
                try:
                    result = subprocess.run(['python', os.path.join(os.path.dirname(__file__), 'scout_engine.py'), '--niche', niche, '--area', area],
                                            capture_output=True, text=True)
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self._send_cors()
                    self.end_headers()
                    self.wfile.write(result.stdout.encode())
                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-type', 'text/plain')
                    self._send_cors()
                    self.end_headers()
                    self.wfile.write(str(e).encode())
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self._send_cors()
                self.end_headers()
                self.wfile.write(b'Missing parameters')
        else:
            self.send_response(404)
            self._send_cors()
            self.end_headers()

    def do_POST(self):
        global hunter_process
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/run-scout':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {}
            niche = data.get('niche')
            area = data.get('area')
            if not niche or not area:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({ 'status': 'error', 'message': 'niche and area are required' }).encode())
                return
            try:
                log_path = os.path.join(os.path.dirname(__file__), 'scout.log')
                log_file = open(log_path, 'a', encoding='utf-8')
                subprocess.Popen(['python', os.path.join(os.path.dirname(__file__), 'scout_engine.py'), '--niche', niche, '--area', area],
                                 stdout=log_file, stderr=log_file)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({ 'status': 'success', 'message': 'Scout Agent sedang berjalan di latar belakang' }).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({ 'status': 'error', 'message': str(e) }).encode())
        elif parsed.path == '/api/sync-supabase':
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM leads')
                rows = cursor.fetchall()
                conn.close()

                payload = []
                for row in rows:
                    d = dict(row)
                    payload.append({
                        'id': d.get('id'),
                        'name': d.get('name'),
                        'niche': d.get('industry') or d.get('niche'),
                        'area': d.get('region') or d.get('area'),
                        'intent_score': d.get('intent_score'),
                        'interest_level': d.get('interest_level'),
                        'phone': d.get('phone'),
                        'email': d.get('email'),
                        'social_link': d.get('social_link') or d.get('source'),
                        'created_at': d.get('created_at'),
                        'processed_at': d.get('processed_at'),
                    })

                resp = requests.post(SUPABASE_URL + '/rest/v1/leads', headers=SUPABASE_HEADERS, json=payload)
                if resp.status_code in (200, 201):
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self._send_cors()
                    self.end_headers()
                    self.wfile.write(json.dumps({ 'status': 'success', 'synced': len(payload) }).encode())
                else:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self._send_cors()
                    self.end_headers()
                    self.wfile.write(json.dumps({ 'status': 'error', 'message': str(resp.status_code) + ' ' + resp.text }).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({ 'status': 'error', 'message': str(e) }).encode())
        elif parsed.path == '/api/start-hunter':
            if hunter_process and hunter_process.poll() is None:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({ 'status': 'info', 'message': 'Hunter sudah sedang berjalan.' }).encode())
                return
            try:
                hunter_script = os.path.join(os.path.dirname(__file__), 'tiktok_hunter.py')
                hunter_process = subprocess.Popen(
                    ['python', hunter_script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({ 'status': 'success', 'message': 'Hunter Started. PID: ' + str(hunter_process.pid) }).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({ 'status': 'error', 'message': str(e) }).encode())
        elif parsed.path == '/api/stop-hunter':
            if not hunter_process or hunter_process.poll() is not None:
                hunter_process = None
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({ 'status': 'info', 'message': 'Hunter tidak sedang berjalan.' }).encode())
                return
            try:
                hunter_process.terminate()
                try:
                    hunter_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    hunter_process.kill()
                hunter_process = None
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({ 'status': 'success', 'message': 'Hunter Stopped.' }).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({ 'status': 'error', 'message': str(e) }).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self._send_cors()
            self.end_headers()
            self.wfile.write(json.dumps({ 'status': 'error', 'message': 'not found' }).encode())

def run_server():
    server = HTTPServer(('localhost', 8000), Handler)
    server.serve_forever()

if __name__ == '__main__':
    run_server()
