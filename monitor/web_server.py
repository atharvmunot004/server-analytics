#!/usr/bin/env python3
# web_server.py - Simple HTTP server to expose metrics on port 9000 for Grafana
# Automatically refreshes metrics every 15 seconds

import os
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

MONITOR_DIR = os.environ.get('MONITOR_DIR', os.path.expanduser('~/monitor'))
METRICS_FILE = os.path.join(MONITOR_DIR, 'out', 'metrics.json')
EVENTS_FILE = os.path.join(MONITOR_DIR, 'out', 'events.log')
PORT = 9000
REFRESH_INTERVAL = 15  # seconds

# Global cache for metrics and events
metrics_cache = []
latest_metric_cache = {}
events_cache = ""
cache_lock = threading.Lock()
last_refresh = 0

def load_metrics():
    """Load metrics from file into cache"""
    global metrics_cache, latest_metric_cache, last_refresh
    
    try:
        metrics = []
        latest = {}
        
        if os.path.exists(METRICS_FILE):
            with open(METRICS_FILE, 'r', buffering=1) as f:
                f.seek(0)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            metric = json.loads(line)
                            metrics.append(metric)
                            latest = metric  # Last valid one is the latest
                        except json.JSONDecodeError:
                            continue
        
        with cache_lock:
            metrics_cache = metrics
            latest_metric_cache = latest
            last_refresh = time.time()
    except Exception as e:
        # Only log errors, not every refresh
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR loading metrics: {e}", flush=True)

def load_events():
    """Load events from file into cache"""
    global events_cache
    
    try:
        if os.path.exists(EVENTS_FILE):
            with open(EVENTS_FILE, 'r', buffering=1) as f:
                f.seek(0)
                content = f.read()
        else:
            content = ''
        
        with cache_lock:
            events_cache = content
    except Exception as e:
        # Only log errors
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR loading events: {e}", flush=True)

def refresh_loop():
    """Background thread that refreshes data every REFRESH_INTERVAL seconds"""
    while True:
        time.sleep(REFRESH_INTERVAL)
        load_metrics()
        load_events()
        # No logging for successful refreshes - only errors are logged

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/latest' or path == '/latest.json':
            self.serve_latest_metric()
        elif path == '/events' or path == '/events.log':
            self.serve_events()
        elif path == '/':
            self.serve_info()
        else:
            self.send_error(404)
    
    def serve_latest_metric(self):
        """Serve the latest metric snapshot from cache"""
        try:
            with cache_lock:
                latest = dict(latest_metric_cache)  # Create a copy of the dict
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(json.dumps(latest, indent=2).encode())
        except BrokenPipeError:
            # Client disconnected, ignore
            pass
        except Exception as e:
            try:
                self.send_error(500, str(e))
            except BrokenPipeError:
                # Client disconnected during error response, ignore
                pass
    
    def serve_events(self):
        """Serve events log from cache"""
        try:
            with cache_lock:
                content = events_cache
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(content.encode())
        except BrokenPipeError:
            # Client disconnected, ignore
            pass
        except Exception as e:
            try:
                self.send_error(500, str(e))
            except BrokenPipeError:
                # Client disconnected during error response, ignore
                pass
    
    def serve_info(self):
        """Serve endpoint information"""
        with cache_lock:
            refresh_time = last_refresh
        
        info = {
            "endpoints": {
                "/latest": "Latest metric snapshot as JSON",
                "/events": "Job events log as plain text"
            },
            "metrics_file": METRICS_FILE,
            "events_file": EVENTS_FILE,
            "refresh_interval_seconds": REFRESH_INTERVAL,
            "last_refresh": refresh_time,
            "metrics_count": len(metrics_cache)
        }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(info, indent=2).encode())
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

def main():
    # Load initial data (silently)
    load_metrics()
    load_events()
    
    # Start background refresh thread
    refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
    refresh_thread.start()
    
    # Start HTTP server
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, MetricsHandler)
    # No startup logging - only errors will be logged
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()

if __name__ == '__main__':
    main()

