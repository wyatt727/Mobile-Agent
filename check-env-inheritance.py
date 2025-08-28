#!/usr/bin/env python3
"""
Check if environment variables are leaking through clean_env
"""
import subprocess
import os

print("=== Environment Inheritance Test ===")
print(f"Parent SHELL: {os.environ.get('SHELL', 'Not set')}")
print(f"Parent HOME: {os.environ.get('HOME', 'Not set')}")

# Test 1: No env parameter (inherits everything)
print("\n--- Test 1: subprocess.run with NO env parameter ---")
result = subprocess.run(['env'], capture_output=True, text=True)
lines = [line for line in result.stdout.split('\n') if 'SHELL=' in line or 'HOME=' in line]
for line in lines:
    print(f"  {line}")

# Test 2: Clean env parameter
print("\n--- Test 2: subprocess.run with CLEAN env parameter ---")
clean_env = {
    'PATH': '/usr/bin:/bin',
    'LC_ALL': 'C',
}
result = subprocess.run(['env'], capture_output=True, text=True, env=clean_env)
lines = [line for line in result.stdout.split('\n') if 'SHELL=' in line or 'HOME=' in line]
if lines:
    print("  ⚠️ SHELL/HOME variables found in clean environment:")
    for line in lines:
        print(f"    {line}")
else:
    print("  ✓ No SHELL/HOME variables in clean environment")

# Test 3: Check what 'which' sees
print("\n--- Test 3: Test 'which claude' with clean env ---")
try:
    result = subprocess.run(['which', 'claude'], capture_output=True, text=True, env=clean_env)
    print(f"  which claude: {result.stdout.strip()}")
    print(f"  Return code: {result.returncode}")
except Exception as e:
    print(f"  Error: {e}")

print("\n--- Test 4: Test direct claude call ---")
try:
    result = subprocess.run(['/usr/local/bin/claude', '--version'], capture_output=True, text=True, env=clean_env)
    print(f"  claude --version: {result.stdout.strip()}")
    print(f"  Return code: {result.returncode}")
    if result.stderr:
        print(f"  stderr: {result.stderr}")
except Exception as e:
    print(f"  Error: {e}")

print("\nIf SHELL variables appear in Test 2, that indicates environment inheritance bugs.")