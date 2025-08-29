#!/usr/bin/env python3
"""
Agent Cleanup Module - Finds and kills all web servers started by Claude Agent
"""
import os
import sys
import psutil
import signal
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import subprocess
import time

logger = logging.getLogger(__name__)

class AgentCleanup:
    """
    Manages cleanup of all Claude Agent web deployments and orphaned servers
    """
    
    def __init__(self):
        # Patterns that identify our servers
        self.web_dir_pattern = '/tmp/web_'
        self.port_range = (8080, 9500)
        self.server_commands = ['http.server', 'flask', 'app.py']
        
        # Stats for reporting
        self.killed_processes = []
        self.cleaned_directories = []
        self.freed_ports = []
        
    def find_agent_servers(self) -> List[Dict]:
        """
        Find all web servers that were likely started by Claude Agent
        
        Returns list of process info dicts
        """
        agent_servers = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd', 'create_time']):
                try:
                    # Get process info safely
                    pid = proc.info.get('pid')
                    name = proc.info.get('name', '')
                    cmdline = proc.info.get('cmdline', [])
                    cwd = None
                    
                    # Try to get working directory
                    try:
                        cwd = proc.cwd()
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        cwd = None
                    
                    # Skip if no command line info
                    if not cmdline:
                        continue
                    
                    cmdline_str = ' '.join(str(x) for x in cmdline)
                    
                    # Check if it's a web server we started
                    is_our_server = False
                    
                    # Method 1: Check if it's http.server or flask
                    if any(server_cmd in cmdline_str for server_cmd in self.server_commands):
                        # Method 2: Check working directory
                        if cwd and cwd.startswith(self.web_dir_pattern):
                            is_our_server = True
                            logger.debug(f"Found by cwd: PID {pid} in {cwd}")
                        
                        # Method 3: Check if running on our port range
                        elif self._check_port_in_range(pid):
                            # Additional verification: command should be python
                            if 'python' in cmdline_str.lower():
                                is_our_server = True
                                logger.debug(f"Found by port: PID {pid}")
                        
                        # Method 4: Check command pattern for our typical usage
                        elif ('-m' in cmdline and 'http.server' in cmdline_str and 
                              any(str(port) in cmdline_str for port in range(8080, 8200))):
                            is_our_server = True
                            logger.debug(f"Found by command pattern: PID {pid}")
                    
                    if is_our_server:
                        # Get additional info
                        connections = []
                        try:
                            connections = proc.connections(kind='inet')
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                        
                        # Find listening port
                        port = None
                        for conn in connections:
                            if conn.status == 'LISTEN':
                                port = conn.laddr.port
                                break
                        
                        # Calculate runtime
                        create_time = proc.info.get('create_time', 0)
                        runtime = time.time() - create_time if create_time else 0
                        
                        server_info = {
                            'pid': pid,
                            'name': name,
                            'cmdline': cmdline_str[:200],  # Truncate for display
                            'cwd': cwd or 'unknown',
                            'port': port,
                            'runtime_seconds': runtime,
                            'runtime_human': self._format_runtime(runtime)
                        }
                        
                        agent_servers.append(server_info)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                    continue
                    
        except Exception as e:
            logger.error(f"Error scanning processes: {e}")
        
        return agent_servers
    
    def _check_port_in_range(self, pid: int) -> bool:
        """Check if process is listening on a port in our range"""
        try:
            proc = psutil.Process(pid)
            connections = proc.connections(kind='inet')
            
            for conn in connections:
                if conn.status == 'LISTEN':
                    port = conn.laddr.port
                    if self.port_range[0] <= port <= self.port_range[1]:
                        return True
        except:
            pass
        return False
    
    def _format_runtime(self, seconds: float) -> str:
        """Format runtime in human-readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        else:
            hours = int(seconds/3600)
            minutes = int((seconds%3600)/60)
            return f"{hours}h {minutes}m"
    
    def kill_server(self, pid: int, force: bool = False) -> bool:
        """
        Kill a server process safely
        
        Args:
            pid: Process ID to kill
            force: Use SIGKILL instead of SIGTERM
        
        Returns:
            True if killed successfully
        """
        try:
            proc = psutil.Process(pid)
            
            # Try graceful termination first
            if not force:
                proc.terminate()  # SIGTERM
                logger.info(f"Sent SIGTERM to PID {pid}")
                
                # Wait up to 2 seconds for graceful shutdown
                try:
                    proc.wait(timeout=2)
                    logger.info(f"Process {pid} terminated gracefully")
                except psutil.TimeoutExpired:
                    logger.warning(f"Process {pid} didn't terminate, forcing...")
                    proc.kill()  # SIGKILL
                    proc.wait(timeout=1)
            else:
                proc.kill()  # SIGKILL immediately
                logger.info(f"Force killed PID {pid}")
            
            self.killed_processes.append(pid)
            return True
            
        except psutil.NoSuchProcess:
            logger.debug(f"Process {pid} already dead")
            return True
        except Exception as e:
            logger.error(f"Failed to kill PID {pid}: {e}")
            return False
    
    def cleanup_directories(self) -> List[str]:
        """
        Clean up web deployment directories
        
        Returns:
            List of cleaned directory paths
        """
        cleaned = []
        
        try:
            # Find all web deployment directories
            tmp_dir = Path('/tmp')
            for item in tmp_dir.iterdir():
                if item.is_dir() and item.name.startswith('web_'):
                    try:
                        # Check if directory is old (optional: only clean if > 1 hour old)
                        age = time.time() - item.stat().st_mtime
                        
                        # Remove directory
                        shutil.rmtree(item)
                        cleaned.append(str(item))
                        self.cleaned_directories.append(str(item))
                        logger.info(f"Removed directory: {item}")
                        
                    except Exception as e:
                        logger.warning(f"Could not remove {item}: {e}")
                        
        except Exception as e:
            logger.error(f"Error cleaning directories: {e}")
        
        return cleaned
    
    def kill_all_agent_servers(self, interactive: bool = True) -> Dict:
        """
        Main method to find and kill all agent servers
        
        Args:
            interactive: If True, ask for confirmation
        
        Returns:
            Dictionary with cleanup results
        """
        print("\n" + "="*60)
        print("CLAUDE AGENT SERVER CLEANUP")
        print("="*60 + "\n")
        
        # Find all servers
        servers = self.find_agent_servers()
        
        if not servers:
            print("✓ No active agent servers found")
            return {'servers_found': 0, 'killed': 0, 'directories_cleaned': 0}
        
        # Display found servers
        print(f"Found {len(servers)} active server(s):\n")
        for i, server in enumerate(servers, 1):
            print(f"{i}. PID {server['pid']}:")
            print(f"   Command: {server['cmdline']}")
            print(f"   Directory: {server['cwd']}")
            if server['port']:
                print(f"   Port: {server['port']}")
                self.freed_ports.append(server['port'])
            print(f"   Runtime: {server['runtime_human']}")
            print()
        
        # Ask for confirmation if interactive
        if interactive:
            response = input("Kill all these servers? (y/n/q): ").lower().strip()
            if response == 'q' or response == 'n':
                print("Cleanup cancelled")
                return {'servers_found': len(servers), 'killed': 0, 'directories_cleaned': 0}
            elif response != 'y':
                print("Invalid response. Cleanup cancelled")
                return {'servers_found': len(servers), 'killed': 0, 'directories_cleaned': 0}
        
        # Kill all servers
        print("\nKilling servers...")
        killed_count = 0
        for server in servers:
            if self.kill_server(server['pid']):
                print(f"  ✓ Killed PID {server['pid']}")
                killed_count += 1
            else:
                print(f"  ✗ Failed to kill PID {server['pid']}")
        
        # Clean up directories
        print("\nCleaning up directories...")
        cleaned_dirs = self.cleanup_directories()
        
        # Final report
        print("\n" + "="*60)
        print("CLEANUP COMPLETE")
        print("="*60)
        print(f"✓ Servers killed: {killed_count}")
        print(f"✓ Directories removed: {len(cleaned_dirs)}")
        if self.freed_ports:
            print(f"✓ Ports freed: {', '.join(map(str, sorted(self.freed_ports)))}")
        
        return {
            'servers_found': len(servers),
            'killed': killed_count,
            'directories_cleaned': len(cleaned_dirs),
            'freed_ports': self.freed_ports
        }
    
    def monitor_mode(self, interval: int = 60):
        """
        Monitor mode - continuously check for orphaned servers
        
        Args:
            interval: Check interval in seconds
        """
        print("Starting monitor mode (Ctrl+C to stop)...")
        
        try:
            while True:
                servers = self.find_agent_servers()
                
                if servers:
                    print(f"\n[{time.strftime('%H:%M:%S')}] Active servers: {len(servers)}")
                    
                    # Check for long-running servers
                    for server in servers:
                        if server['runtime_seconds'] > 3600:  # Over 1 hour
                            print(f"  ⚠️  PID {server['pid']} running for {server['runtime_human']}")
                            
                            # Optionally auto-kill very old servers
                            if server['runtime_seconds'] > 86400:  # Over 24 hours
                                print(f"  🔴 Auto-killing PID {server['pid']} (>24 hours)")
                                self.kill_server(server['pid'])
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\nMonitor mode stopped")

# Integration with existing managers
def integrate_cleanup():
    """
    Integrate cleanup with existing WebDeploymentManager and LanguageExecutor
    """
    try:
        # Try to import and use existing tracking
        from claude_agent.core.web_deployment import get_deployment_manager
        from claude_agent.core.language_executor import LanguageExecutor
        
        manager = get_deployment_manager()
        
        # Use manager's shutdown_all first
        if hasattr(manager, 'shutdown_all'):
            print("Using WebDeploymentManager cleanup...")
            manager.shutdown_all()
        
        # Then clean up any orphaned servers
        cleanup = AgentCleanup()
        cleanup.kill_all_agent_servers(interactive=False)
        
    except ImportError:
        # Fallback to standalone cleanup
        cleanup = AgentCleanup()
        cleanup.kill_all_agent_servers()

# Command-line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Claude Agent Server Cleanup')
    parser.add_argument('--force', '-f', action='store_true', 
                       help='Skip confirmation prompt')
    parser.add_argument('--monitor', '-m', action='store_true',
                       help='Run in monitor mode')
    parser.add_argument('--interval', '-i', type=int, default=60,
                       help='Monitor check interval in seconds')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    cleanup = AgentCleanup()
    
    if args.monitor:
        cleanup.monitor_mode(args.interval)
    else:
        cleanup.kill_all_agent_servers(interactive=not args.force)