#!/usr/bin/env python3
"""
Debug wrapper for subprocess to track ALL subprocess calls
This will help us find exactly which call is loading .zshrc
"""
import subprocess
import sys
import os
import traceback
from functools import wraps

# Store original subprocess functions
_original_run = subprocess.run
_original_Popen = subprocess.Popen
_original_call = subprocess.call
_original_check_output = subprocess.check_output

def log_subprocess(func_name, args, kwargs):
    """Log subprocess call details"""
    print(f"\n🔍 SUBPROCESS CALL: {func_name}", file=sys.stderr)
    print(f"   Command: {args[0] if args else 'None'}", file=sys.stderr)
    
    # Check environment
    env = kwargs.get('env')
    if env is None:
        print(f"   Environment: INHERITED (DANGEROUS!)", file=sys.stderr)
        print(f"   SHELL in os.environ: {os.environ.get('SHELL', 'Not set')}", file=sys.stderr)
        print(f"   HOME in os.environ: {os.environ.get('HOME', 'Not set')}", file=sys.stderr)
        # This is likely the culprit!
        print(f"   ⚠️  This call will inherit your shell environment!", file=sys.stderr)
    else:
        print(f"   Environment: CLEAN ({len(env)} vars)", file=sys.stderr)
        shell_vars = ['SHELL', 'HOME', 'ZSH', 'BASH', 'ENV', 'BASH_ENV']
        for var in shell_vars:
            if var in env:
                print(f"   ⚠️  {var} in clean env: {env[var]}", file=sys.stderr)
        
        # Show all environment variables in clean env
        if len(env) < 10:  # Only if not too many
            print(f"   Clean env contents: {dict(env)}", file=sys.stderr)
    
    # Print call stack
    stack = traceback.extract_stack()
    print(f"   Call stack:", file=sys.stderr)
    for frame in stack[-5:-1]:  # Show more frames
        print(f"     {frame.filename}:{frame.lineno} in {frame.name}", file=sys.stderr)
    
    print(f"   {'='*60}", file=sys.stderr)

def debug_run(*args, **kwargs):
    log_subprocess('subprocess.run', args, kwargs)
    return _original_run(*args, **kwargs)

def debug_Popen(*args, **kwargs):
    log_subprocess('subprocess.Popen', args, kwargs)
    return _original_Popen(*args, **kwargs)

def debug_call(*args, **kwargs):
    log_subprocess('subprocess.call', args, kwargs)
    return _original_call(*args, **kwargs)

def debug_check_output(*args, **kwargs):
    log_subprocess('subprocess.check_output', args, kwargs)
    return _original_check_output(*args, **kwargs)

# Monkey patch subprocess
subprocess.run = debug_run
subprocess.Popen = debug_Popen
subprocess.call = debug_call
subprocess.check_output = debug_check_output

print("🔍 Subprocess debugging enabled!", file=sys.stderr)
print(f"🔍 Current SHELL: {os.environ.get('SHELL', 'Not set')}", file=sys.stderr)
print(f"🔍 Current HOME: {os.environ.get('HOME', 'Not set')}", file=sys.stderr)
print("🔍 All subprocess calls will be logged to stderr", file=sys.stderr)