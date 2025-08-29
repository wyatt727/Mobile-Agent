#!/usr/bin/env python3
"""
Advanced Web Deployment System for NetHunter Agent
Handles single and multi-file deployments with database support
Enhanced with audio service protection and process isolation
"""
import os
import sys
import subprocess
import tempfile
import time
import json
import sqlite3
import logging
import signal
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
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
        
        # Reserved ports for audio and system services
        self.reserved_ports: Set[int] = {
            4713,  # PulseAudio TCP
            8000,  # NetHunter Audio Manager
            4712,  # PulseAudio native protocol
            6600,  # MPD (Music Player Daemon)
            8001,  # Alternative audio streaming
        }
        
        # Track our process groups for safe cleanup
        self.process_groups = {}  # timestamp -> pgid mapping
        
        logger.info(f"WebDeploymentManager initialized with reserved ports: {self.reserved_ports}")
        
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
            deployment_info.update(self._start_backend_server(deploy_dir, with_database, timestamp))
        else:
            deployment_info.update(self._start_static_server(deploy_dir, timestamp))
        
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
    
    def _start_static_server(self, deploy_dir: Path, timestamp: int = None) -> Dict[str, Any]:
        """Start a simple Python HTTP server"""
        port = self._find_available_port()
        
        try:
            # Preserve audio environment variables
            env = os.environ.copy()
            # Ensure PULSE_SERVER is passed for audio connectivity
            if 'PULSE_SERVER' not in env:
                env['PULSE_SERVER'] = 'tcp:127.0.0.1:4713'
            
            # Log file for debugging without stdout competition
            log_file = deploy_dir / 'server.log'
            log_handle = open(log_file, 'w')
            
            # Start server in background with process isolation
            # On macOS, use start_new_session OR preexec_fn, not both
            if sys.platform == 'darwin':
                server_process = subprocess.Popen(
                    ['python3', '-m', 'http.server', str(port)],
                    cwd=deploy_dir,
                    stdout=log_handle,  # Log instead of DEVNULL
                    stderr=subprocess.STDOUT,  # Combine stderr with stdout
                    text=True,
                    env=env,  # Pass environment with PULSE_SERVER
                    start_new_session=True  # Create new process group
                )
            else:
                # On Linux/NetHunter, use both for complete isolation
                server_process = subprocess.Popen(
                    ['python3', '-m', 'http.server', str(port)],
                    cwd=deploy_dir,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,  # Pass environment with PULSE_SERVER
                    start_new_session=True,
                    preexec_fn=os.setsid
                )
            
            # Store process group ID for safe cleanup
            if timestamp:
                try:
                    pgid = os.getpgid(server_process.pid)
                    self.process_groups[timestamp] = pgid
                except:
                    # Fallback if we can't get pgid
                    self.process_groups[timestamp] = server_process.pid
            
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
    
    def _start_backend_server(self, deploy_dir: Path, has_database: bool, timestamp: int = None) -> Dict[str, Any]:
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
            
            # Preserve audio environment variables
            env = os.environ.copy()
            # Ensure PULSE_SERVER is passed for audio connectivity
            if 'PULSE_SERVER' not in env:
                env['PULSE_SERVER'] = 'tcp:127.0.0.1:4713'
            
            # Log file for debugging without stdout competition
            log_file = deploy_dir / 'flask.log'
            log_handle = open(log_file, 'w')
            
            # Start Flask server with process isolation
            # On macOS, use start_new_session OR preexec_fn, not both
            if sys.platform == 'darwin':
                server_process = subprocess.Popen(
                    ['python3', 'app.py'],
                    cwd=deploy_dir,
                    stdout=log_handle,  # Log instead of DEVNULL
                    stderr=subprocess.STDOUT,  # Combine stderr with stdout
                    text=True,
                    env=env,  # Pass environment with PULSE_SERVER
                    start_new_session=True  # Create new process group
                )
            else:
                # On Linux/NetHunter, use both for complete isolation
                server_process = subprocess.Popen(
                    ['python3', 'app.py'],
                    cwd=deploy_dir,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,  # Pass environment with PULSE_SERVER
                    start_new_session=True,
                    preexec_fn=os.setsid
                )
            
            # Store process group ID for safe cleanup
            if timestamp:
                try:
                    pgid = os.getpgid(server_process.pid)
                    self.process_groups[timestamp] = pgid
                except:
                    # Fallback if we can't get pgid
                    self.process_groups[timestamp] = server_process.pid
            
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
                    
                    # Launch browser
                    launch_result = subprocess.run(
                        ['adb', 'shell',
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
        """Find an available port, avoiding audio service ports"""
        import socket
        
        if start is None:
            start = self.base_port
        
        # Ensure we don't start in reserved range
        while start in self.reserved_ports:
            start += 1
        
        for port in range(start, start + 100):
            # Skip reserved audio ports
            if port in self.reserved_ports:
                logger.debug(f"Skipping reserved audio port {port}")
                continue
            
            # Check if port is actually available
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(('', port))
                    logger.info(f"Found available port {port} (avoided audio ports)")
                    return port
                except OSError:
                    continue
        
        # Fallback with warning
        logger.warning(f"Could not find free port, using {start + 100}")
        return start + 100
    
    def stop_deployment(self, timestamp: int) -> bool:
        """Stop a deployment and clean up safely without affecting audio services"""
        if timestamp not in self.deployments:
            return False
        
        deployment = self.deployments[timestamp]
        
        # Safe process termination with verification
        if 'pid' in deployment:
            try:
                # Verify process belongs to us before killing
                if self._verify_our_process(deployment['pid'], timestamp):
                    # Kill entire process group to clean up properly
                    if timestamp in self.process_groups:
                        pgid = self.process_groups[timestamp]
                        try:
                            # Send SIGTERM to process group for graceful shutdown
                            os.killpg(pgid, signal.SIGTERM)
                            logger.info(f"Sent SIGTERM to process group {pgid}")
                            
                            # Give processes time to clean up
                            time.sleep(0.5)
                            
                            # Force kill if still running
                            try:
                                os.killpg(pgid, signal.SIGKILL)
                                logger.info(f"Force killed process group {pgid}")
                            except ProcessLookupError:
                                pass  # Already terminated
                                
                            del self.process_groups[timestamp]
                        except Exception as e:
                            logger.warning(f"Error killing process group: {e}")
                            # Fallback to individual process
                            subprocess.run(['kill', '-TERM', str(deployment['pid'])], 
                                         timeout=2, capture_output=True)
                    else:
                        # Fallback for older deployments
                        subprocess.run(['kill', '-TERM', str(deployment['pid'])], 
                                     timeout=2, capture_output=True)
                    
                    logger.info(f"Stopped server PID {deployment['pid']}")
                else:
                    logger.warning(f"PID {deployment['pid']} does not belong to our deployment")
            except Exception as e:
                logger.error(f"Error stopping process: {e}")
        
        # Clean up directory
        if 'directory' in deployment:
            try:
                shutil.rmtree(deployment['directory'])
                logger.info(f"Removed {deployment['directory']}")
            except Exception as e:
                logger.warning(f"Could not remove directory: {e}")
        
        del self.deployments[timestamp]
        return True
    
    def _verify_our_process(self, pid: int, timestamp: int) -> bool:
        """Verify that a PID belongs to our deployment and not audio services"""
        try:
            # Check if process exists
            if not psutil.pid_exists(pid):
                return False
            
            proc = psutil.Process(pid)
            
            # Get process command line
            cmdline = ' '.join(proc.cmdline())
            
            # Check if it's an audio-related process (safety check)
            audio_keywords = ['pulse', 'audio', 'kex-audio', 'termux-audio', 
                            'paplay', 'pactl', 'pacmd', 'mpd', 'alsa']
            if any(keyword in cmdline.lower() for keyword in audio_keywords):
                logger.warning(f"PID {pid} appears to be an audio service, refusing to kill")
                return False
            
            # Check if it's a web server process
            web_keywords = ['http.server', 'flask', 'app.py', 'python3']
            if any(keyword in cmdline for keyword in web_keywords):
                # Additional check: verify working directory matches deployment
                deployment = self.deployments.get(timestamp)
                if deployment and 'directory' in deployment:
                    try:
                        proc_cwd = proc.cwd()
                        if deployment['directory'] in proc_cwd:
                            return True
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
                
                # If we started it with our process group, it's ours
                if timestamp in self.process_groups:
                    try:
                        pgid = os.getpgid(pid)
                        if pgid == self.process_groups[timestamp]:
                            return True
                    except:
                        pass
            
            return False
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def list_deployments(self) -> List[Dict[str, Any]]:
        """List all active deployments"""
        # Clean up any dead deployments first
        self._cleanup_dead_deployments()
        return list(self.deployments.values())
    
    def _cleanup_dead_deployments(self):
        """Remove deployments with dead processes"""
        dead_timestamps = []
        for timestamp, deployment in self.deployments.items():
            if 'pid' in deployment:
                if not psutil.pid_exists(deployment['pid']):
                    dead_timestamps.append(timestamp)
                    logger.info(f"Found dead deployment {timestamp}, cleaning up")
        
        for timestamp in dead_timestamps:
            # Clean up directory only, process already dead
            deployment = self.deployments[timestamp]
            if 'directory' in deployment:
                try:
                    shutil.rmtree(deployment['directory'])
                except:
                    pass
            del self.deployments[timestamp]
            if timestamp in self.process_groups:
                del self.process_groups[timestamp]
    
    def shutdown_all(self):
        """Safely shutdown all deployments"""
        logger.info("Shutting down all web deployments...")
        timestamps = list(self.deployments.keys())
        for timestamp in timestamps:
            self.stop_deployment(timestamp)
        logger.info("All web deployments stopped")

# Global instance
_manager = None

def get_deployment_manager() -> WebDeploymentManager:
    """Get or create global deployment manager"""
    global _manager
    if _manager is None:
        _manager = WebDeploymentManager()
    return _manager