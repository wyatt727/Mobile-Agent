#!/usr/bin/env python3
"""
Audio Service Protection Module for NetHunter Agent
Monitors and protects audio services from interference
"""
import os
import subprocess
import psutil
import logging
import signal
import time
from typing import List, Dict, Set, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioServiceProtector:
    """
    Protects audio services from being accidentally terminated
    and monitors their health
    """
    
    def __init__(self):
        # Critical audio service identifiers
        self.audio_processes = {
            'pulseaudio', 'pulse', 'paplay', 'pactl', 'pacmd',
            'kex-audio', 'termux-audio', 'audio-warmstart',
            'mpd', 'alsa', 'jackd', 'pipewire'
        }
        
        # Critical audio ports that must remain available
        self.audio_ports = {
            4713,  # PulseAudio TCP
            4712,  # PulseAudio native
            8000,  # NetHunter Audio Manager
            6600,  # MPD
            8001,  # Alternative audio streaming
        }
        
        # Track protected PIDs
        self.protected_pids: Set[int] = set()
        
        # Web server port range (to keep separate from audio)
        self.web_port_start = 8080
        self.web_port_end = 9500
        
    def scan_audio_services(self) -> Dict[str, List[Dict]]:
        """
        Scan for running audio services
        Returns dict with service info
        """
        audio_services = {
            'processes': [],
            'ports': [],
            'health_status': 'unknown'
        }
        
        try:
            # Find audio-related processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    name = proc.info['name'] or ''
                    
                    # Check if it's an audio service
                    if any(audio_key in cmdline.lower() or audio_key in name.lower() 
                           for audio_key in self.audio_processes):
                        
                        audio_services['processes'].append({
                            'pid': proc.info['pid'],
                            'name': name,
                            'cmdline': cmdline[:100],  # Truncate for readability
                            'status': proc.status()
                        })
                        
                        # Mark as protected
                        self.protected_pids.add(proc.info['pid'])
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Check audio ports
            for conn in psutil.net_connections():
                if conn.laddr and conn.laddr.port in self.audio_ports:
                    audio_services['ports'].append({
                        'port': conn.laddr.port,
                        'status': conn.status,
                        'pid': conn.pid if conn.pid else 'unknown'
                    })
            
            # Determine health status
            pulse_running = any('pulse' in p['name'].lower() 
                               for p in audio_services['processes'])
            ports_active = len(audio_services['ports']) > 0
            
            if pulse_running and ports_active:
                audio_services['health_status'] = 'healthy'
            elif pulse_running or ports_active:
                audio_services['health_status'] = 'partial'
            else:
                audio_services['health_status'] = 'not_running'
                
        except Exception as e:
            logger.error(f"Error scanning audio services: {e}")
            audio_services['health_status'] = 'error'
        
        return audio_services
    
    def protect_process(self, pid: int) -> bool:
        """
        Mark a process as protected from termination
        """
        try:
            if psutil.pid_exists(pid):
                self.protected_pids.add(pid)
                logger.info(f"Protected PID {pid}")
                return True
        except:
            pass
        return False
    
    def is_protected(self, pid: int) -> bool:
        """
        Check if a PID is protected
        """
        return pid in self.protected_pids
    
    def verify_audio_health(self) -> Dict[str, any]:
        """
        Comprehensive audio health check
        """
        health = {
            'pulse_server': False,
            'ports_available': [],
            'ports_blocked': [],
            'recommendations': []
        }
        
        # Check PULSE_SERVER environment variable
        pulse_server = os.environ.get('PULSE_SERVER', '')
        if pulse_server:
            health['pulse_server'] = pulse_server
            
            # Try to connect to PulseAudio
            if 'tcp:' in pulse_server:
                host_port = pulse_server.replace('tcp:', '').split(':')
                if len(host_port) == 2:
                    port = int(host_port[1])
                    if self._check_port_listening(port):
                        health['pulse_server_status'] = 'listening'
                    else:
                        health['pulse_server_status'] = 'not_listening'
                        health['recommendations'].append(
                            f"PulseAudio not listening on {pulse_server}. "
                            "Run: ~/bin/kex-audio-up --quiet"
                        )
        
        # Check critical ports
        for port in self.audio_ports:
            if self._check_port_listening(port):
                health['ports_available'].append(port)
            else:
                health['ports_blocked'].append(port)
        
        # Generate recommendations
        if health['ports_blocked']:
            blocked = ', '.join(map(str, health['ports_blocked']))
            health['recommendations'].append(
                f"Audio ports {blocked} are not available. "
                "Check for conflicting services."
            )
        
        # Check for audio warmstart
        warmstart_running = any('warmstart' in str(p.cmdline()) 
                               for p in psutil.process_iter() 
                               if hasattr(p, 'cmdline'))
        health['warmstart_active'] = warmstart_running
        
        if not warmstart_running:
            health['recommendations'].append(
                "Audio warmstart not running. "
                "Run: ~/bin/termux-audio-warmstart.sh &"
            )
        
        return health
    
    def _check_port_listening(self, port: int) -> bool:
        """
        Check if a port is listening
        """
        try:
            for conn in psutil.net_connections():
                if (conn.laddr and conn.laddr.port == port and 
                    conn.status == 'LISTEN'):
                    return True
        except:
            pass
        return False
    
    def restart_audio_services(self) -> Dict[str, str]:
        """
        Attempt to restart audio services if they're not running
        """
        results = {}
        
        try:
            # Check if audio services are already running
            status = self.scan_audio_services()
            
            if status['health_status'] == 'healthy':
                results['status'] = 'already_running'
                return results
            
            # Try to start kex-audio-up
            kex_audio_path = Path.home() / 'bin' / 'kex-audio-up'
            if kex_audio_path.exists():
                try:
                    subprocess.run(
                        [str(kex_audio_path), '--quiet'],
                        capture_output=True,
                        timeout=5,
                        check=False
                    )
                    time.sleep(2)
                    results['kex_audio'] = 'started'
                except Exception as e:
                    results['kex_audio'] = f'failed: {e}'
            
            # Try to start termux-audio-warmstart
            warmstart_path = Path.home() / 'bin' / 'termux-audio-warmstart.sh'
            if warmstart_path.exists():
                try:
                    subprocess.Popen(
                        [str(warmstart_path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    results['warmstart'] = 'started'
                except Exception as e:
                    results['warmstart'] = f'failed: {e}'
            
            # Test audio with beep
            try:
                subprocess.run(
                    ['paplay', '/usr/share/sounds/freedesktop/stereo/bell.oga'],
                    capture_output=True,
                    timeout=2
                )
                results['test_beep'] = 'success'
            except:
                results['test_beep'] = 'failed'
                
        except Exception as e:
            results['error'] = str(e)
        
        return results
    
    def get_safe_web_port(self) -> int:
        """
        Get a safe port for web services that won't conflict with audio
        """
        import socket
        
        for port in range(self.web_port_start, self.web_port_end):
            # Skip audio ports
            if port in self.audio_ports:
                continue
            
            # Check if port is free
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(('', port))
                    return port
                except OSError:
                    continue
        
        # Fallback
        return self.web_port_end
    
    def monitor_and_report(self) -> str:
        """
        Generate a comprehensive audio status report
        """
        report = []
        report.append("=== Audio Service Status Report ===\n")
        
        # Scan current services
        status = self.scan_audio_services()
        
        # Health status
        report.append(f"Overall Health: {status['health_status'].upper()}\n")
        
        # Running processes
        if status['processes']:
            report.append("\nActive Audio Processes:")
            for proc in status['processes']:
                report.append(f"  - PID {proc['pid']}: {proc['name']} [{proc['status']}]")
        else:
            report.append("\n⚠️  No audio processes detected!")
        
        # Port status
        if status['ports']:
            report.append("\nActive Audio Ports:")
            for port_info in status['ports']:
                report.append(f"  - Port {port_info['port']}: {port_info['status']}")
        else:
            report.append("\n⚠️  No audio ports active!")
        
        # Detailed health check
        health = self.verify_audio_health()
        
        report.append(f"\nPULSE_SERVER: {health.get('pulse_server', 'Not set')}")
        
        if health.get('recommendations'):
            report.append("\nRecommendations:")
            for rec in health['recommendations']:
                report.append(f"  • {rec}")
        
        # Protected PIDs
        if self.protected_pids:
            report.append(f"\nProtected PIDs: {', '.join(map(str, self.protected_pids))}")
        
        return '\n'.join(report)

# Global instance
_protector = None

def get_audio_protector() -> AudioServiceProtector:
    """Get or create global audio protector"""
    global _protector
    if _protector is None:
        _protector = AudioServiceProtector()
    return _protector

def protect_audio_services():
    """Quick function to protect all current audio services"""
    protector = get_audio_protector()
    status = protector.scan_audio_services()
    
    protected_count = len(protector.protected_pids)
    logger.info(f"Protected {protected_count} audio service PIDs")
    
    return status

def check_audio_health():
    """Quick health check"""
    protector = get_audio_protector()
    return protector.monitor_and_report()

if __name__ == "__main__":
    # Run health check when executed directly
    print(check_audio_health())