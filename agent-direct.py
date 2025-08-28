#!/usr/bin/python3
"""
Direct Python agent launcher that completely bypasses shell
This version should NEVER load .zshrc because it's pure Python
"""
import os
import sys
import subprocess
from pathlib import Path

# Immediately strip ALL shell environment variables
DANGEROUS_VARS = ['SHELL', 'HOME', 'USER', 'ZSH', 'BASH', 'ENV', 'BASH_ENV', 'ZDOTDIR', 'PYTHONSTARTUP']
for var in DANGEROUS_VARS:
    if var in os.environ:
        print(f"🔍 REMOVING DANGEROUS VAR: {var}={os.environ[var]}", file=sys.stderr)
        del os.environ[var]

# Debug environment 
print(f"🔍 DIRECT AGENT STARTUP:", file=sys.stderr)
print(f"   AGENT_DEBUG_SUBPROCESS: {os.environ.get('AGENT_DEBUG_SUBPROCESS', 'NOT SET')}", file=sys.stderr)
print(f"   Remaining env vars: {len(os.environ)}", file=sys.stderr)

# Get agent location
AGENT_DIR = Path("/root/.mobile-agent")
AGENT_SCRIPT = AGENT_DIR / "agent"

# Use os.execv to completely replace this process with the real agent
# This prevents any shell initialization
try:
    # Set up minimal environment
    clean_env = {
        'PATH': '/usr/bin:/bin:/usr/local/bin:/sbin:/usr/sbin',
        'PYTHONPATH': str(AGENT_DIR),
        'PYTHONIOENCODING': 'utf-8',
        'PYTHONNOUSERSITE': '1',
        'PYTHONDONTWRITEBYTECODE': '1'
    }
    
    # Pass through debug flag
    if os.environ.get('AGENT_DEBUG_SUBPROCESS') == '1':
        clean_env['AGENT_DEBUG_SUBPROCESS'] = '1'
        
    # Clear environment and set clean one
    os.environ.clear()
    os.environ.update(clean_env)
    
    print(f"🔍 EXEC: python3 {AGENT_SCRIPT} with args {sys.argv[1:]}", file=sys.stderr)
    
    # Replace this process entirely - no shell inheritance possible
    os.execv("/usr/bin/python3", ["python3", str(AGENT_SCRIPT)] + sys.argv[1:])
    
except Exception as e:
    print(f"🔍 DIRECT LAUNCH FAILED: {e}", file=sys.stderr)
    sys.exit(1)