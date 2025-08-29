#!/usr/bin/env python3
"""
Language Executor - Handles execution of code blocks with NetHunter-specific languages
"""
import os
import sys
import subprocess
import tempfile
import time
import logging
from pathlib import Path
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class LanguageExecutor:
    """
    Executes code blocks based on language identifiers.
    Supports NetHunter-specific execution modes.
    """
    
    # Class-level list to keep server processes alive
    _active_servers = []
    
    def __init__(self, timeout: int = 120):
        """
        Initialize Language Executor.
        
        Args:
            timeout: Execution timeout in seconds
        """
        self.timeout = timeout
        self.temp_dir = Path("/tmp")
        
        # Check if we're in NetHunter environment
        self.is_nethunter = any([
            Path('/etc/nethunter').exists(),
            Path('/data/local/nhsystem').exists(),
            os.getenv('NETHUNTER_MODE') == '1'
        ])
        
        # Check ADB availability
        self.has_adb = self._check_command('adb')
        
        logger.info(f"LanguageExecutor initialized. NetHunter: {self.is_nethunter}, ADB: {self.has_adb}")
    
    def _check_command(self, command: str) -> bool:
        """Check if a command is available."""
        try:
            subprocess.run(['which', command], capture_output=True, check=True)
            return True
        except:
            return False
    
    def execute(self, code: str, language: str) -> Tuple[bool, str, str]:
        """
        Execute code based on language identifier.
        
        Args:
            code: Code to execute
            language: Language identifier (bash, python, android, android-root, html, etc.)
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        # Normalize language identifier
        language = language.lower().strip()
        
        # Map alternative names
        language_map = {
            'shell': 'bash',
            'sh': 'bash',
            'py': 'python',
            'python3': 'python',
            'js': 'javascript',
            'node': 'javascript'
        }
        
        language = language_map.get(language, language)
        
        logger.info(f"Executing {language} code block ({len(code)} bytes)")
        
        try:
            # Route to appropriate executor
            if language in ['bash', 'shell']:
                return self._execute_bash(code)
            elif language == 'python':
                return self._execute_python(code)
            elif language == 'javascript':
                return self._execute_javascript(code)
            elif language == 'android':
                return self._execute_android(code)
            elif language == 'android-root':
                return self._execute_android_root(code)
            elif language == 'html':
                return self._execute_html(code)
            else:
                return False, "", f"Unsupported language: {language}"
        
        except Exception as e:
            logger.error(f"Error executing {language} code: {e}")
            return False, "", str(e)
    
    def _execute_bash(self, code: str) -> Tuple[bool, str, str]:
        """Execute bash/shell code."""
        try:
            # Write to temporary script for better execution
            script_file = self.temp_dir / f"script_{int(time.time())}.sh"
            script_file.write_text(code)
            script_file.chmod(0o755)
            
            result = subprocess.run(
                ['/bin/sh', str(script_file)],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # Cleanup
            script_file.unlink(missing_ok=True)
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", f"Execution timed out after {self.timeout} seconds"
        except Exception as e:
            return False, "", str(e)
    
    def _execute_python(self, code: str) -> Tuple[bool, str, str]:
        """Execute Python code."""
        try:
            result = subprocess.run(
                ['python3', '-c', code],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", f"Execution timed out after {self.timeout} seconds"
        except Exception as e:
            return False, "", str(e)
    
    def _execute_javascript(self, code: str) -> Tuple[bool, str, str]:
        """Execute JavaScript code with Node.js."""
        if not self._check_command('node'):
            return False, "", "Node.js not installed"
        
        try:
            result = subprocess.run(
                ['node', '-e', code],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", f"Execution timed out after {self.timeout} seconds"
        except Exception as e:
            return False, "", str(e)
    
    def _execute_android(self, code: str) -> Tuple[bool, str, str]:
        """
        Execute code on Android via adb shell.
        This runs commands on the Android system (not as root).
        """
        if not self.has_adb:
            return False, "", "ADB not available"
        
        try:
            # Check device connection
            devices_result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if 'device' not in devices_result.stdout:
                return False, "", "No ADB device connected"
            
            # Execute via adb shell
            result = subprocess.run(
                ['adb', 'shell', code],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", f"Execution timed out after {self.timeout} seconds"
        except Exception as e:
            return False, "", str(e)
    
    def _execute_android_root(self, code: str) -> Tuple[bool, str, str]:
        """
        Execute code on Android as root via adb shell su.
        This runs commands with root privileges.
        """
        if not self.has_adb:
            return False, "", "ADB not available"
        
        try:
            # Check device connection
            devices_result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if 'device' not in devices_result.stdout:
                return False, "", "No ADB device connected"
            
            # Execute as root via su
            # Escape single quotes in the code
            escaped_code = code.replace("'", "'\\''")
            
            result = subprocess.run(
                ['adb', 'shell', 'su', '-c', f"sh -c '{escaped_code}'"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", f"Execution timed out after {self.timeout} seconds"
        except Exception as e:
            return False, "", str(e)
    
    def _execute_html(self, code: str) -> Tuple[bool, str, str]:
        """
        Execute HTML code by creating a web server and launching browser.
        This is the NetHunter web deployment feature.
        """
        try:
            import random
            import socket
            
            # Create directory for web files
            timestamp = int(time.time())
            web_dir = self.temp_dir / f"web_{timestamp}"
            web_dir.mkdir(exist_ok=True)
            
            # Write HTML file
            html_file = web_dir / "index.html"
            html_file.write_text(code)
            
            # Find a truly available port
            def find_free_port():
                # Reserved audio service ports to avoid
                reserved_ports = {4713, 8000, 4712, 6600, 8001}
                
                for _ in range(20):  # More attempts
                    port = random.randint(8080, 9000)
                    
                    # Skip reserved audio ports
                    if port in reserved_ports:
                        continue
                    
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        try:
                            s.bind(('', port))
                            s.close()
                            logger.info(f"Found free port {port} (avoided audio ports)")
                            return port
                        except:
                            continue
                
                # Fallback to a safe port
                logger.warning("Using fallback port 9090")
                return 9090
            
            port = find_free_port()
            
            # Start web server detached to survive parent exit
            log_file = web_dir / 'server.log'
            
            # Preserve audio environment for web apps that need sound
            env = os.environ.copy()
            # Ensure PULSE_SERVER is available for audio playback
            if 'PULSE_SERVER' not in env:
                env['PULSE_SERVER'] = 'tcp:127.0.0.1:4713'
            
            # Use log file to avoid stdout competition while preserving debug info
            log_file = web_dir / 'server.log'
            with open(log_file, 'w') as log_handle:
                # Start server process with complete isolation
                # Platform-specific process isolation
                if sys.platform == 'darwin':
                    # macOS: use only start_new_session
                    server_process = subprocess.Popen(
                        ['python3', '-m', 'http.server', str(port)],
                        cwd=str(web_dir),
                        stdout=log_handle,  # Log to file instead of DEVNULL
                        stderr=subprocess.STDOUT,  # Combine stderr with stdout
                        env=env,  # Pass environment with audio support
                        start_new_session=True  # Creates new session for independence
                    )
                else:
                    # Linux/NetHunter: use both for complete isolation
                    server_process = subprocess.Popen(
                        ['python3', '-m', 'http.server', str(port)],
                        cwd=str(web_dir),
                        stdout=log_handle,
                        stderr=subprocess.STDOUT,
                        env=env,  # Pass environment with audio support
                        start_new_session=True,
                        preexec_fn=os.setsid  # Complete process group isolation
                    )
            
            # Store server process to keep it alive
            LanguageExecutor._active_servers.append({
                'process': server_process,
                'port': port,
                'dir': str(web_dir),
                'pid': server_process.pid
            })
            
            # Give server time to start and verify it's accessible
            time.sleep(1)
            
            # Verify server is actually serving
            import urllib.request
            for _ in range(5):  # Try 5 times
                try:
                    with urllib.request.urlopen(f'http://localhost:{port}', timeout=1) as response:
                        if response.status == 200:
                            break
                except:
                    time.sleep(0.5)
                    continue
            
            # Check if server is actually running
            if server_process.poll() is not None:
                # Process ended, something went wrong
                stdout, stderr = server_process.communicate()
                error_msg = f"Server failed to start: {stderr.decode('utf-8', errors='ignore')}"
                return False, "", error_msg
            
            output = f"✓ Web server started at http://localhost:{port}\n"
            output += f"✓ Server PID: {server_process.pid}\n"
            output += f"✓ Files served from: {web_dir}\n"
            output += f"✓ HTML file created at: {html_file}\n"
            output += f"✓ Active servers: {len(LanguageExecutor._active_servers)}\n"
            
            # Try to launch browser
            if self.has_adb and self.is_nethunter:
                # NetHunter environment - launch on Android
                try:
                    # Set up port forwarding
                    subprocess.run(
                        ['adb', 'reverse', f'tcp:{port}', f'tcp:{port}'],
                        capture_output=True,
                        timeout=5
                    )
                    
                    # Launch browser on Android
                    subprocess.run(
                        ['adb', 'shell', 
                         f'am start -a android.intent.action.VIEW -d http://localhost:{port}'],
                        capture_output=True,
                        timeout=5
                    )
                    
                    output += f"✓ Browser launched on Android device\n"
                    
                except Exception as e:
                    output += f"⚠ Could not launch Android browser: {e}\n"
            else:
                # MacOS/Linux environment - open locally without shell
                try:
                    import platform
                    url = f'http://localhost:{port}'
                    
                    if platform.system() == 'Darwin':  # macOS
                        # Use open command directly without shell
                        subprocess.run(['open', url], check=False)
                    elif platform.system() == 'Linux':
                        # Try xdg-open first, then fallback
                        try:
                            subprocess.run(['xdg-open', url], check=False)
                        except:
                            subprocess.run(['firefox', url], check=False)
                    else:
                        # Windows fallback - use os.startfile instead of shell
                        os.startfile(url)
                    
                    output += f"✓ Browser launched locally\n"
                except Exception as e:
                    output += f"⚠ Could not launch local browser: {e}\n"
            
            return True, output, ""
            
        except Exception as e:
            return False, "", f"Failed to deploy HTML: {e}"


# Global executor instance
_executor = None

def get_executor() -> LanguageExecutor:
    """Get or create global language executor."""
    global _executor
    if _executor is None:
        _executor = LanguageExecutor()
    return _executor