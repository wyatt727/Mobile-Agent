# Agent Kill Command - Documentation

## Overview
The `agent-kill` command finds and terminates all web servers started by Claude Agent, preventing resource leaks from orphaned processes.

## The Problem It Solves
Every HTML code block creates a new web server that runs **forever** due to:
- `subprocess.Popen()` with `start_new_session=True`
- Process detachment from parent
- No automatic cleanup on exit
- No timeout mechanism

This leads to:
- Multiple Python processes consuming memory
- Occupied ports (8080-9500)
- Cluttered `/tmp` directories
- Eventually system resource exhaustion

## How It Works

### Process Identification Strategy
The cleanup utility identifies agent servers using multiple methods:

1. **Working Directory Check**: Looks for processes in `/tmp/web_*` directories
2. **Port Range Check**: Identifies servers on ports 8080-9500
3. **Command Pattern Matching**: Finds `python -m http.server` with our port range
4. **Process Name Filtering**: Checks for `http.server`, `flask`, `app.py`

### Safe Cleanup Process
1. **Graceful Termination**: Sends SIGTERM first
2. **Timeout Wait**: Waits 2 seconds for graceful shutdown
3. **Force Kill**: Uses SIGKILL if process doesn't terminate
4. **Directory Cleanup**: Removes `/tmp/web_*` directories
5. **Port Tracking**: Reports freed ports

## Usage

### Command Line

```bash
# List active servers without killing
agent-kill --list

# Kill all servers (interactive)
agent-kill

# Kill all servers (no confirmation)
agent-kill --yes

# Minimal output
agent-kill --quiet --yes
```

### From Python

```python
from claude_agent.core.agent_cleanup import AgentCleanup

# Create cleanup instance
cleanup = AgentCleanup()

# Find servers
servers = cleanup.find_agent_servers()
print(f"Found {len(servers)} active servers")

# Kill all servers
result = cleanup.kill_all_agent_servers(interactive=False)
print(f"Killed {result['killed']} servers")
```

### Integrated with ClaudeAgent

```python
from claude_agent.core import ClaudeAgent

agent = ClaudeAgent()

# Generate some web apps...
agent.chat("Create a website")
agent.chat("Create another website")

# Clean up all servers
result = agent.cleanup_servers(force=True)
print(f"Cleaned up {result['killed']} servers")
```

## Features

### Server Detection
- Finds servers by working directory pattern
- Identifies by port range (8080-9500)
- Tracks runtime duration
- Shows command line and PID

### Cleanup Statistics
- Number of servers killed
- Directories removed
- Ports freed
- Runtime of each server

### Monitor Mode
```bash
# Monitor for orphaned servers
python3 claude_agent/core/agent_cleanup.py --monitor

# Auto-kill servers older than 24 hours
python3 claude_agent/core/agent_cleanup.py --monitor --interval 3600
```

## Implementation Details

### Key Components

1. **AgentCleanup Class** (`agent_cleanup.py`)
   - `find_agent_servers()`: Locates all agent servers
   - `kill_server()`: Safely terminates a process
   - `cleanup_directories()`: Removes deployment directories
   - `kill_all_agent_servers()`: Main cleanup method

2. **Process Identification**
   - Uses psutil for cross-platform process management
   - Checks process working directory
   - Verifies listening ports
   - Matches command patterns

3. **Safety Measures**
   - Won't kill non-agent processes
   - Confirms before killing (unless forced)
   - Handles permission errors gracefully
   - Reports what was cleaned

## Real-World Example

Before cleanup:
```bash
$ ps aux | grep http.server
user  14836  python3 -m http.server 8646  # 20 hours old
user  15353  python3 -m http.server 8464  # 20 hours old
user  76959  python3 -m http.server 8080  # 1 hour old
```

After `agent-kill --yes`:
```
✓ Servers killed: 3
✓ Directories removed: 3
✓ Ports freed: 8080, 8464, 8646
```

## Best Practices

### For Users
1. Run `agent-kill` periodically during development
2. Use `agent-kill --list` to check for orphaned servers
3. Run cleanup before system shutdown

### For Integration
1. Call `cleanup_servers()` at session end
2. Implement timeout for long-running servers
3. Consider auto-cleanup after N hours

## Future Improvements

### Possible Enhancements
1. **Automatic Cleanup**: Register atexit handler
2. **Server Timeout**: Auto-kill after configurable duration
3. **Resource Limits**: Maximum concurrent servers
4. **Server Reuse**: Reuse existing servers for same port
5. **Systemd Integration**: Run as system service

### Prevention Strategies
```python
# Better server management (future implementation)
class ManagedWebServer:
    def __init__(self, lifetime=3600):
        self.lifetime = lifetime
        self.timer = Timer(lifetime, self.cleanup)
        self.timer.start()
    
    def cleanup(self):
        # Auto-cleanup after lifetime expires
        pass
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Some processes may require elevated permissions
   - Solution: Run with appropriate permissions

2. **Process Not Found**
   - Server already terminated
   - Solution: Cleanup will continue with other servers

3. **Directory Not Removed**
   - Directory in use or permission issue
   - Solution: Manual cleanup with `rm -rf /tmp/web_*`

## Summary

The `agent-kill` command is essential for managing Claude Agent web servers. It prevents resource leaks by:
- Finding all orphaned servers
- Killing them safely
- Cleaning up directories
- Reporting freed resources

Run it periodically to keep your system clean!