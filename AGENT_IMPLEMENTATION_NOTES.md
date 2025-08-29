# Agent Implementation Notes

## Current Status on macOS

**What's Actually Being Used:**
- `/usr/local/bin/agent` → symlink to `/Users/pentester/Tools/Mobile-Agent/agent` (Python script)
- The Python `agent` script handles all commands directly
- **The `agent kill` command WORKS** - it's integrated into the Python script

## File Purposes

### Core Files
- **`agent`** (Python) - Main agent script, handles all logic including `kill` command
- **`agent-kill`** - Standalone Python script for killing servers (alternative method)

### NetHunter-Specific (NOT used on macOS)
- **`agent-noshrc.c`** - C wrapper for NetHunter to bypass shell initialization
  - Has hardcoded paths: `/root/.mobile-agent/`
  - Would be compiled during NetHunter installation
  - NOT compiled or used on macOS

### Shell Wrappers (Fallbacks)
- **`agent-noshell`** - Shell wrapper using `/bin/sh`
- **`agent-busybox`** - Shell wrapper for systems where sh→zsh

## How Installation Works

### On macOS:
1. `install-mobile.sh` tries to compile `agent-noshrc.c` but fails (wrong paths)
2. Falls back to using Python `agent` directly
3. Creates symlink: `/usr/local/bin/agent` → `./agent`

### On NetHunter:
1. `install-mobile.sh` compiles `agent-noshrc.c` with correct paths
2. Creates symlink: `/usr/local/bin/agent` → `./agent-noshrc`
3. C wrapper calls Python script with clean environment

## The `agent kill` Command

**Current Implementation:**
- Added to Python `agent` script (lines 264-309)
- Handles commands: `kill`, `cleanup`, `kill-servers`
- Uses `AgentCleanup` class from `claude_agent/core/agent_cleanup.py`

**How to Use:**
```bash
# Kill all web servers
agent kill

# Alternative standalone method
python3 agent-kill

# With options
python3 agent-kill --list  # Just list servers
python3 agent-kill --yes   # Skip confirmation
```

## No Compilation Needed on macOS

The C wrapper (`agent-noshrc.c`) is **NOT needed** on macOS because:
1. Hardcoded paths are wrong for macOS
2. Python script works fine directly
3. The kill command is already integrated

## Summary

✅ **The `agent kill` command is working correctly on macOS**
- Integrated into the Python `agent` script
- No C compilation needed
- Ready to use as-is