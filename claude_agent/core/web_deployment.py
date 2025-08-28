#!/usr/bin/env python3
"""
Advanced Web Deployment System for NetHunter Agent
Handles single and multi-file deployments with database support
"""
import os
import subprocess
import tempfile
import time
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import shutil

logger = logging.getLogger(__name__)

class WebDeploymentManager:
    """
    Manages sophisticated web application deployments
    """
    
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.deployments = {}  # Track active deployments
        self.base_port = 8080
        
    def deploy_web_app(self, 
                       html_content: str = None,
                       files: Dict[str, str] = None,
                       with_backend: bool = False,
                       with_database: bool = False) -> Dict[str, Any]:
        """
        Deploy a web application with various configurations
        
        Args:
            html_content: Main HTML content (for single-file apps)
            files: Dictionary of filename -> content for multi-file apps
            with_backend: Whether to start a Python backend
            with_database: Whether to create an SQLite database
            
        Returns:
            Deployment information dictionary
        """
        # Create deployment directory
        timestamp = int(time.time())
        deploy_dir = Path(f'/tmp/web_deploy_{timestamp}')
        deploy_dir.mkdir(exist_ok=True, parents=True)
        
        deployment_info = {
            'directory': str(deploy_dir),
            'timestamp': timestamp,
            'files': []
        }
        
        # Deploy files
        if html_content:
            # Single HTML file deployment
            index_path = deploy_dir / 'index.html'
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            deployment_info['files'].append('index.html')
            logger.info(f"Created index.html in {deploy_dir}")
            
        if files:
            # Multi-file deployment
            for filename, content in files.items():
                file_path = deploy_dir / filename
                # Create subdirectories if needed
                file_path.parent.mkdir(exist_ok=True, parents=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                deployment_info['files'].append(filename)
                logger.info(f"Created {filename}")
        
        # Set up database if requested
        if with_database:
            db_path = deploy_dir / 'app.db'
            deployment_info['database'] = self._setup_database(db_path)
        
        # Start appropriate server
        if with_backend:
            deployment_info.update(self._start_backend_server(deploy_dir, with_database))
        else:
            deployment_info.update(self._start_static_server(deploy_dir))
        
        # Set up port forwarding and launch browser
        if deployment_info.get('port'):
            self._setup_access(deployment_info['port'])
        
        # Store deployment info
        self.deployments[timestamp] = deployment_info
        
        return deployment_info
    
    def _setup_database(self, db_path: Path) -> Dict[str, Any]:
        """Create and initialize SQLite database"""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Create sample tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert sample data
            cursor.execute("INSERT INTO items (name, data) VALUES (?, ?)", 
                         ("Sample Item", json.dumps({"key": "value"})))
            cursor.execute("INSERT INTO users (username, email) VALUES (?, ?)",
                         ("admin", "admin@example.com"))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Database created at {db_path}")
            return {
                'path': str(db_path),
                'tables': ['items', 'users']
            }
            
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            return {'error': str(e)}
    
    def _start_static_server(self, deploy_dir: Path) -> Dict[str, Any]:
        """Start a simple Python HTTP server"""
        port = self._find_available_port()
        
        try:
            # Start server in background
            server_process = subprocess.Popen(
                ['python3', '-m', 'http.server', str(port)],
                cwd=deploy_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Give server time to start
            time.sleep(1)
            
            # Check if server started
            if server_process.poll() is not None:
                stdout, stderr = server_process.communicate()
                return {
                    'success': False,
                    'error': f'Server failed to start: {stderr}'
                }
            
            logger.info(f"Static server started on port {port}")
            
            return {
                'success': True,
                'server_type': 'static',
                'port': port,
                'pid': server_process.pid,
                'url': f'http://localhost:{port}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _start_backend_server(self, deploy_dir: Path, has_database: bool) -> Dict[str, Any]:
        """Start a Flask backend server with API support"""
        port = self._find_available_port()
        
        # Create Flask app
        flask_app = deploy_dir / 'app.py'
        
        app_content = f'''
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import sqlite3
from datetime import datetime

app = Flask(__name__, static_folder='.')
CORS(app)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/status')
def status():
    return jsonify({{
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'database': {has_database}
    }})
'''
        
        if has_database:
            app_content += '''
@app.route('/api/items')
def get_items():
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM items')
    items = [{'id': row[0], 'name': row[1], 'data': row[2]} 
             for row in cursor.fetchall()]
    conn.close()
    return jsonify(items)

@app.route('/api/items', methods=['POST'])
def create_item():
    data = request.json
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO items (name, data) VALUES (?, ?)',
                   (data.get('name'), json.dumps(data.get('data', {}))))
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return jsonify({'id': item_id, 'success': True})

@app.route('/api/users')
def get_users():
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = [{'id': row[0], 'username': row[1], 'email': row[2]} 
             for row in cursor.fetchall()]
    conn.close()
    return jsonify(users)
'''
        
        app_content += f'''
if __name__ == '__main__':
    app.run(host='0.0.0.0', port={port}, debug=False)
'''
        
        with open(flask_app, 'w') as f:
            f.write(app_content)
        
        try:
            # Install Flask if needed (should be in requirements)
            subprocess.run(
                ['pip3', 'install', '--quiet', 'flask', 'flask-cors'],
                timeout=30,
                capture_output=True
            )
            
            # Start Flask server
            server_process = subprocess.Popen(
                ['python3', 'app.py'],
                cwd=deploy_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for server to start
            time.sleep(2)
            
            # Check if running
            if server_process.poll() is not None:
                stdout, stderr = server_process.communicate()
                return {
                    'success': False,
                    'error': f'Flask server failed: {stderr}'
                }
            
            logger.info(f"Flask backend started on port {port}")
            
            return {
                'success': True,
                'server_type': 'flask',
                'port': port,
                'pid': server_process.pid,
                'url': f'http://localhost:{port}',
                'api_endpoints': [
                    '/api/status',
                    '/api/items' if has_database else None,
                    '/api/users' if has_database else None
                ]
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _setup_access(self, port: int):
        """Set up port forwarding and launch browser"""
        try:
            # Check if ADB is available
            adb_check = subprocess.run(
                ['which', 'adb'],
                capture_output=True,
                timeout=2
            )
            
            if adb_check.returncode == 0:
                # Set up reverse port forwarding
                reverse_result = subprocess.run(
                    ['adb', 'reverse', f'tcp:{port}', f'tcp:{port}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if reverse_result.returncode == 0:
                    logger.info(f"Port {port} forwarding established")
                    
                    # Launch browser (bypass shell initialization)
                    launch_result = subprocess.run(
                        ['adb', 'shell', 'env', '-i', 'sh', '-c',
                         f'am start -a android.intent.action.VIEW -d http://localhost:{port}'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if launch_result.returncode == 0:
                        logger.info("Browser launched on device")
                    else:
                        logger.warning("Could not launch browser")
                else:
                    logger.warning(f"Port forwarding failed: {reverse_result.stderr}")
            else:
                logger.info("ADB not available - server accessible locally only")
                
        except Exception as e:
            logger.warning(f"Access setup failed: {e}")
    
    def _find_available_port(self, start: int = None) -> int:
        """Find an available port"""
        import socket
        
        if start is None:
            start = self.base_port
        
        for port in range(start, start + 100):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(('', port))
                    return port
                except OSError:
                    continue
        
        return start  # Fallback
    
    def stop_deployment(self, timestamp: int) -> bool:
        """Stop a deployment and clean up"""
        if timestamp not in self.deployments:
            return False
        
        deployment = self.deployments[timestamp]
        
        # Kill server process
        if 'pid' in deployment:
            try:
                subprocess.run(['kill', str(deployment['pid'])], timeout=5)
                logger.info(f"Stopped server PID {deployment['pid']}")
            except:
                pass
        
        # Clean up directory
        if 'directory' in deployment:
            try:
                shutil.rmtree(deployment['directory'])
                logger.info(f"Removed {deployment['directory']}")
            except:
                pass
        
        del self.deployments[timestamp]
        return True
    
    def list_deployments(self) -> List[Dict[str, Any]]:
        """List all active deployments"""
        return list(self.deployments.values())

# Global instance
_manager = None

def get_deployment_manager() -> WebDeploymentManager:
    """Get or create global deployment manager"""
    global _manager
    if _manager is None:
        _manager = WebDeploymentManager()
    return _manager