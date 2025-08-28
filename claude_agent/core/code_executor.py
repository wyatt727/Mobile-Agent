#!/usr/bin/env python3
"""
Code Executor - Handles code execution with dependency management
"""
import os
import subprocess
import sys
import time
import tempfile
import logging
import re
import importlib.util
from pathlib import Path
from typing import Optional, Set, List, Tuple
from datetime import datetime

from claude_agent.utils.models import ExecutionResult, CodeLanguage
from claude_agent.core.adb_client import AdbClient


logger = logging.getLogger(__name__)


class CodeExecutor:
    """Handles code execution with proper error handling and dependency management."""
    
    def __init__(
        self,
        timeout: int = 60,
        track_dependencies: bool = True,
        auto_install_packages: bool = True,
        save_executed_code: bool = True,
        generated_code_dir: str = "generated_code",
        nethunter_mode: bool = False,
        adb_path: str = "adb"
    ):
        """
        Initialize code executor. 
        
        Args:
            timeout: Execution timeout in seconds
            track_dependencies: Whether to track and install Python dependencies
            auto_install_packages: Whether to automatically install missing packages
            save_executed_code: Whether to save executed code to files
            generated_code_dir: Directory to save generated code
            nethunter_mode: If True, agent is running in a NetHunter chroot and uses ADB for host interactions.
            adb_path: Path to the ADB executable.
        """
        self.timeout = timeout
        self.track_dependencies = track_dependencies
        self.auto_install_packages = auto_install_packages
        self.save_executed_code = save_executed_code
        self.generated_code_dir = Path(generated_code_dir)
        self.nethunter_mode = nethunter_mode
        
        self.adb_client: Optional[AdbClient] = None
        if self.nethunter_mode:
            self.adb_client = AdbClient(adb_path=adb_path)
            logger.info("CodeExecutor initialized in NetHunter mode. ADB client enabled.")
        
        # Track installed packages to avoid repeated checks
        self.installed_packages: Set[str] = set()
        
        # Ensure generated code directory exists
        if self.save_executed_code:
            self.generated_code_dir.mkdir(parents=True, exist_ok=True)
    
    def execute(
        self,
        code: str,
        language: str = "python",
        save_file: bool = None
    ) -> ExecutionResult:
        """
        Execute code in specified language.
        
        Args:
            code: Code to execute
            language: Programming language
            save_file: Override save_executed_code setting
            
        Returns:
            ExecutionResult with output and status
        """
        # Normalize language
        language = CodeLanguage.normalize(language)
        
        # Save code if requested
        if save_file is None:
            save_file = self.save_executed_code
        
        if save_file:
            self._save_code_to_file(code, language)
        
        # Execute based on language
        start_time = time.time()
        
        try:
            if language == "python":
                result = self._execute_python(code)
            elif language == "shell":
                result = self._execute_shell(code)
            elif language == "javascript":
                result = self._execute_javascript(code)
            else:
                result = ExecutionResult(
                    success=False,
                    output="",
                    error=f"Unsupported language: {language}",
                    return_code=-1,
                    language=language
                )
            
            # Add execution time
            result.execution_time = time.time() - start_time
            
            # Log result
            if result.success:
                logger.info(f"Successfully executed {language} code in {result.execution_time:.2f}s")
            else:
                logger.warning(f"Failed to execute {language} code: {result.error}")
            
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error executing {language} code: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                return_code=-1,
                language=language,
                execution_time=time.time() - start_time
            )
    
    def _execute_python(self, code: str) -> ExecutionResult:
        """Execute Python code."""
        if self.nethunter_mode and self.adb_client:
            # In NetHunter mode, push script to device and execute via ADB
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".py", encoding='utf-8') as tmp_file:
                tmp_file.write(code)
                local_script_path = Path(tmp_file.name)
            
            remote_script_path = "/data/local/tmp/script.py" # Fixed path on device
            
            try:
                # Push script
                push_rc, push_stdout, push_stderr = self.adb_client.push(str(local_script_path), remote_script_path)
                if push_rc != 0:
                    return ExecutionResult(
                        success=False,
                        output=push_stdout,
                        error=f"ADB push failed: {push_stderr}",
                        return_code=push_rc,
                        language="python"
                    )
                
                # Execute script on device with su
                exec_cmd = f"chmod 755 {remote_script_path} && python {remote_script_path}"
                exec_rc, exec_stdout, exec_stderr = self.adb_client.shell(exec_cmd, su=True, timeout=self.timeout)
                
                return ExecutionResult(
                    success=exec_rc == 0,
                    output=exec_stdout,
                    error=exec_stderr,
                    return_code=exec_rc,
                    language="python"
                )
            finally:
                # Clean up local temp file
                if local_script_path.exists():
                    local_script_path.unlink()
                # Clean up remote temp file (best effort)
                self.adb_client.shell(f"rm {remote_script_path}", su=True)
        else:
            # Standard Python execution (chroot/local)
            # Handle dependencies BEFORE execution
            if self.track_dependencies and self.auto_install_packages:
                missing_deps = self._check_python_dependencies(code)
                if missing_deps:
                    logger.info(f"Auto-installing missing packages: {missing_deps}")
                    self._install_python_packages(missing_deps)
            
            # Execute code
            try:
                # Use minimal environment to avoid shell initialization
                clean_env = {
                    'PATH': os.environ.get('PATH', '/usr/bin:/bin:/usr/local/bin'),
                    'HOME': os.environ.get('HOME', ''),
                    'USER': os.environ.get('USER', ''),
                    'LANG': os.environ.get('LANG', 'en_US.UTF-8'),
                    'LC_ALL': os.environ.get('LC_ALL', 'en_US.UTF-8'),
                    'PYTHONIOENCODING': 'utf-8',
                    'PYTHONPATH': os.environ.get('PYTHONPATH', '')
                }
                
                result = subprocess.run(
                    [sys.executable, "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    env=clean_env
                )
                
                return ExecutionResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    return_code=result.returncode,
                    language="python"
                )
                
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"Execution timed out after {self.timeout} seconds",
                    return_code=-1,
                    language="python",
                    timeout=True
                )
    
    def _execute_shell(self, code: str) -> ExecutionResult:
        """Execute shell commands."""
        if self.nethunter_mode and self.adb_client:
            # In NetHunter mode, execute shell commands via ADB with su
            rc, stdout, stderr = self.adb_client.shell(code, su=True, timeout=self.timeout)
            return ExecutionResult(
                success=rc == 0,
                output=stdout,
                error=stderr,
                return_code=rc,
                language="shell"
            )
        else:
            # Standard shell execution (chroot/local)
            # Use /bin/sh to avoid loading user's shell config (.zshrc, .bashrc, etc.)
            shell = '/bin/sh'
            
            # Check if this is a pip install command
            if self._is_pip_install(code):
                packages = self._extract_pip_packages(code)
                if packages:
                    logger.info(f"Detected pip install for packages: {packages}")
                    # Add to installed packages to avoid re-installation
                    self.installed_packages.update(packages)
            
            try:
                # Write code to a temp file and execute it to avoid shell initialization
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                    f.write(code)
                    temp_script = f.name
                
                os.chmod(temp_script, 0o755)
                
                result = subprocess.run(
                    [shell, temp_script],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                # Clean up temp file
                os.unlink(temp_script)
                
                return ExecutionResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    return_code=result.returncode,
                    language="shell"
                )
                
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"Execution timed out after {self.timeout} seconds",
                    return_code=-1,
                    language="shell",
                    timeout=True
                )
    
    def _execute_javascript(self, code: str) -> ExecutionResult:
        """Execute JavaScript code using Node.js."""
        if self.nethunter_mode and self.adb_client:
            # For JavaScript in NetHunter, we'll assume it's meant to run on the host
            # This would require Node.js to be installed on the Android device.
            # For simplicity, we'll push and execute it similarly to Python.
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".js", encoding='utf-8') as tmp_file:
                tmp_file.write(code)
                local_script_path = Path(tmp_file.name)
            
            remote_script_path = "/data/local/tmp/script.js" # Fixed path on device
            
            try:
                # Push script
                push_rc, push_stdout, push_stderr = self.adb_client.push(str(local_script_path), remote_script_path)
                if push_rc != 0:
                    return ExecutionResult(
                        success=False,
                        output=push_stdout,
                        error=f"ADB push failed: {push_stderr}",
                        return_code=push_rc,
                        language="javascript"
                    )
                
                # Execute script on device with su (assuming node is in PATH on device)
                exec_cmd = f"chmod 755 {remote_script_path} && node {remote_script_path}"
                exec_rc, exec_stdout, exec_stderr = self.adb_client.shell(exec_cmd, su=True, timeout=self.timeout)
                
                return ExecutionResult(
                    success=exec_rc == 0,
                    output=exec_stdout,
                    error=exec_stderr,
                    return_code=exec_rc,
                    language="javascript"
                )
            finally:
                # Clean up local temp file
                if local_script_path.exists():
                    local_script_path.unlink()
                # Clean up remote temp file (best effort)
                self.adb_client.shell(f"rm {remote_script_path}", su=True)
        else:
            # Check if Node.js is available
            if not self._check_node_available():
                return ExecutionResult(
                    success=False,
                    output="",
                    error="Node.js is not installed. Please install Node.js to execute JavaScript code.",
                    return_code=-1,
                    language="javascript"
                )
            
            try:
                result = subprocess.run(
                    ["node", "-e", code],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                return ExecutionResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    return_code=result.returncode,
                    language="javascript"
                )
                
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"Execution timed out after {self.timeout} seconds",
                    return_code=-1,
                    language="javascript",
                    timeout=True
                )
    
    def _check_python_dependencies(self, code: str) -> Set[str]:
        """
        Check for missing Python dependencies in code.
        
        Args:
            code: Python code to check
            
        Returns:
            Set of missing package names
        """
        # Common import name to package name mappings
        IMPORT_TO_PACKAGE = {
            'cv2': 'opencv-python',
            'sklearn': 'scikit-learn',
            'PIL': 'pillow',
            'yaml': 'pyyaml',
            'bs4': 'beautifulsoup4',
            'dotenv': 'python-dotenv',
            'flask_cors': 'flask-cors',
            'googleapiclient': 'google-api-python-client',
            'OpenSSL': 'pyOpenSSL',
            'lxml': 'lxml',
            'pymongo': 'pymongo',
            'psycopg2': 'psycopg2-binary',
            'MySQLdb': 'mysqlclient',
            'sqlite3': None,  # Built-in, no install needed
            'pyppeteer': 'pyppeteer',
            'selenium': 'selenium',
            'webdriver_manager': 'webdriver-manager',
            'playwright': 'playwright',
        }
        
        # Extract import statements
        import_pattern = re.compile(r'^\s*(?:import|from)\s+([\w\.]+)', re.MULTILINE)
        imports = import_pattern.findall(code)
        
        # Extract base module names
        modules = {imp.split('.')[0] for imp in imports}
        
        # Check which modules are missing
        missing = set()
        for module in modules:
            # Skip built-in modules
            if module in sys.builtin_module_names:
                continue
            
            # Skip if explicitly marked as built-in
            if module in IMPORT_TO_PACKAGE and IMPORT_TO_PACKAGE[module] is None:
                continue
            
            # Skip already checked/installed
            if module in self.installed_packages:
                continue
            
            # Quick check if module is available
            try:
                # Use __import__ for a quick check
                __import__(module)
                self.installed_packages.add(module)
            except ImportError:
                # Map import name to package name
                package_name = IMPORT_TO_PACKAGE.get(module, module)
                missing.add(package_name)
                logger.debug(f"Missing Python module: {module} (package: {package_name})")
        
        return missing
    
    def _install_python_packages(self, packages: Set[str]):
        """
        Install Python packages using pip.
        
        Args:
            packages: Set of package names to install
        """
        for package in packages:
            logger.info(f"Installing Python package: {package}")
            
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    self.installed_packages.add(package)
                    logger.info(f"Successfully installed {package}")
                else:
                    logger.warning(f"Failed to install {package}: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"Installation of {package} timed out")
            except Exception as e:
                logger.warning(f"Error installing {package}: {e}")
    
    def _check_node_available(self) -> bool:
        """
        Check if Node.js is available."""
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _save_code_to_file(self, code: str, language: str) -> Optional[Path]:
        """
        Save code to a file for record keeping.
        
        Args:
            code: Code to save
            language: Programming language
            
        Returns:
            Path to saved file or None if save failed
        """
        # Determine file extension
        extensions = {
            "python": ".py",
            "shell": ".sh",
            "javascript": ".js",
            "bash": ".sh",
            "sh": ".sh"
        }
        ext = extensions.get(language, ".txt")
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.generated_code_dir / f"code_{timestamp}_{language}{ext}"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(code)
            
            logger.debug(f"Saved {language} code to {filename}")
            return filename
            
        except Exception as e:
            logger.warning(f"Failed to save code to file: {e}")
            return None
    
    
    def _is_pip_install(self, code: str) -> bool:
        """Check if a shell command is a pip install command."""
        # Common patterns for pip install
        patterns = [
            r'\bpip\s+install\b',
            r'\bpip3\s+install\b',
            r'\bpython\s+-m\s+pip\s+install\b',
            r'\bpython3\s+-m\s+pip\s+install\b'
        ]
        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        return False
    
    def _extract_pip_packages(self, code: str) -> Set[str]:
        """Extract package names from pip install command."""
        packages = set()
        
        # Match pip install [options] package1 package2 ...
        pattern = r'pip[3]?\s+install\s+(?:--[a-z-]+\s+)*([^\n;|&]+)'
        match = re.search(pattern, code, re.IGNORECASE)
        
        if match:
            # Split by spaces and filter out options
            parts = match.group(1).split()
            for part in parts:
                # Skip options and requirements files
                if not part.startswith('-') and not part.startswith('.') and part != 'requirements.txt':
                    # Handle package==version or package>=version
                    package = re.split(r'[<>=!~]', part)[0]
                    if package:
                        packages.add(package)
        
        return packages
    
    def cleanup_generated_files(self, older_than_days: int = 7):
        """
        Clean up old generated code files.
        
        Args:
            older_than_days: Delete files older than this many days
        """
        if not self.generated_code_dir.exists():
            return
        
        cutoff_time = time.time() - (older_than_days * 24 * 3600)
        deleted_count = 0
        
        for file_path in self.generated_code_dir.glob("code_*"):
            if file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old generated code files")
