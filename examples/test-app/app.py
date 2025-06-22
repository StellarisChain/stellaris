#!/usr/bin/env python3
"""
Simple example application for testing the VoxaCommunications app deployment system.
"""

import json
import time
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            response = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>VoxaCommunications Test App</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                    .status {{ background: #e8f5e8; padding: 20px; border-radius: 5px; }}
                    .info {{ background: #e8f4ff; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🚀 VoxaCommunications Test App</h1>
                    <div class="status">
                        <h2>Status: Running</h2>
                        <p><strong>Time:</strong> {datetime.now().isoformat()}</p>
                        <p><strong>App ID:</strong> {os.getenv('VOXA_APP_ID', 'unknown')}</p>
                        <p><strong>Instance ID:</strong> {os.getenv('VOXA_INSTANCE_ID', 'unknown')}</p>
                        <p><strong>Node ID:</strong> {os.getenv('VOXA_NODE_ID', 'unknown')}</p>
                    </div>
                    
                    <div class="info">
                        <h3>Environment Variables</h3>
                        <ul>
                            {''.join(f'<li><strong>{k}:</strong> {v}</li>' for k, v in os.environ.items() if k.startswith('VOXA_'))}
                        </ul>
                    </div>
                    
                    <div class="info">
                        <h3>Available Endpoints</h3>
                        <ul>
                            <li><a href="/health">Health Check</a></li>
                            <li><a href="/metrics">Metrics</a></li>
                            <li><a href="/info">App Info</a></li>
                        </ul>
                    </div>
                </div>
            </body>
            </html>
            """
            self.wfile.write(response.encode())
            
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            health_data = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "uptime": time.time() - start_time,
                "app_id": os.getenv('VOXA_APP_ID'),
                "instance_id": os.getenv('VOXA_INSTANCE_ID'),
                "node_id": os.getenv('VOXA_NODE_ID')
            }
            self.wfile.write(json.dumps(health_data).encode())
            
        elif self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            metrics_data = {
                "requests_served": request_counter,
                "uptime_seconds": time.time() - start_time,
                "memory_info": self._get_memory_info(),
                "timestamp": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(metrics_data).encode())
            
        elif self.path == '/info':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            info_data = {
                "app_name": "voxa-test-app",
                "version": "1.0.0",
                "description": "Test application for VoxaCommunications deployment system",
                "author": "VoxaCommunications Team",
                "capabilities": ["web-server", "health-check", "metrics"],
                "environment": {k: v for k, v in os.environ.items() if k.startswith('VOXA_')},
                "started_at": start_time_iso,
                "pid": os.getpid()
            }
            self.wfile.write(json.dumps(info_data, indent=2).encode())
            
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found')
        
        # Update request counter
        global request_counter
        request_counter += 1
    
    def _get_memory_info(self):
        """Get memory usage information"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            return {
                "rss": memory_info.rss,
                "vms": memory_info.vms,
                "percent": process.memory_percent()
            }
        except ImportError:
            return {"error": "psutil not available"}
    
    def log_message(self, format, *args):
        """Override to add timestamp to logs"""
        print(f"[{datetime.now().isoformat()}] {format % args}")

def main():
    """Main application entry point"""
    global start_time, start_time_iso, request_counter
    
    start_time = time.time()
    start_time_iso = datetime.now().isoformat()
    request_counter = 0
    
    # Configuration
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8080'))
    
    print(f"Starting VoxaCommunications Test App...")
    print(f"App ID: {os.getenv('VOXA_APP_ID', 'unknown')}")
    print(f"Instance ID: {os.getenv('VOXA_INSTANCE_ID', 'unknown')}")
    print(f"Node ID: {os.getenv('VOXA_NODE_ID', 'unknown')}")
    print(f"Listening on {host}:{port}")
    
    # Start HTTP server
    server = HTTPServer((host, port), AppHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nShutting down...")
        server.shutdown()
        print("Server stopped.")

if __name__ == "__main__":
    main()
