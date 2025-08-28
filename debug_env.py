#!/usr/bin/env python3
"""Debug script to check environment variables"""
import os
import sys

print("=== Environment Debug ===")
print(f"Python: {sys.executable}")
print(f"Platform: {sys.platform}")
print("\n=== Shell-related variables ===")
for var in ['SHELL', 'ZSH', 'BASH', 'ENV', 'BASH_ENV', 'ZSH_VERSION', 'BASH_VERSION', 'HOME', 'USER']:
    val = os.environ.get(var)
    if val:
        print(f"{var}={val}")

print("\n=== PATH ===")
print(os.environ.get('PATH', 'PATH not set'))

print("\n=== All environment variables ===")
for key, value in sorted(os.environ.items()):
    if len(value) > 100:
        value = value[:100] + "..."
    print(f"{key}={value}")

print("\n=== Process info ===")
print(f"PID: {os.getpid()}")
print(f"PPID: {os.getppid()}")

# Check if .zshrc exists
import pathlib
zshrc_paths = [
    pathlib.Path.home() / '.zshrc',
    pathlib.Path('/root/.zshrc'),
    pathlib.Path('/home/user/.zshrc'),
]

print("\n=== Shell RC files ===")
for path in zshrc_paths:
    if path.exists():
        print(f"Found: {path}")