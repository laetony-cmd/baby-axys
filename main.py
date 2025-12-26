"""Test imports"""
import os
import json
import urllib.request
import urllib.parse
import smtplib
import ssl
import gzip
import csv
import io
import re
import threading
import time
print("[1] Basic imports OK")

# Import anthropic
ANTHROPIC_OK = False
try:
    import anthropic
    ANTHROPIC_OK = True
    print("[2] anthropic OK")
except Exception as e:
    print(f"[2] anthropic FAIL: {e}")

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from math import radians, cos, sin, asin, sqrt
print("[3] Standard libs OK")

# Internet
INTERNET_OK = False
try:
    from duckduckgo_search import DDGS
    import trafilatura
    INTERNET_OK = True
    print("[4] Internet libs OK")
except Exception as e:
    print(f"[4] Internet FAIL: {e}")

# DB
DB_OK = False
try:
    from db import get_db
    db = get_db()
    if db.connect():
        DB_OK = True
        print("[5] DB OK")
    else:
        print("[5] DB connect failed")
except Exception as e:
    print(f"[5] DB FAIL: {e}")

print(f"\nStatus: ANTHROPIC={ANTHROPIC_OK}, INTERNET={INTERNET_OK}, DB={DB_OK}")

# Serveur minimal
class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "anthropic": ANTHROPIC_OK,
            "internet": INTERNET_OK,
            "db": DB_OK
        }).encode())

port = int(os.environ.get('PORT', 8080))
print(f"Starting on port {port}")
server = HTTPServer(('0.0.0.0', port), TestHandler)
server.serve_forever()
