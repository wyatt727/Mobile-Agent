# Audio Service Protection Solution

## Problem
Web app generation was potentially interfering with audio services in NetHunter due to:
- Port conflicts (PulseAudio uses 4713, Audio Manager uses 8000)
- Process resource competition (stdout/stderr)
- Accidental termination of audio processes
- Lack of process isolation

## Solution Implemented

### 1. Port Reservation System
- Reserved audio ports: 4713, 8000, 4712, 6600, 8001
- Web deployments automatically skip these ports
- Port selection algorithm checks availability before binding

### 2. Process Isolation with Audio Support
- Web servers run in separate process groups using `start_new_session=True`
- Platform-specific handling (macOS vs Linux/NetHunter)
- **stdout/stderr redirected to log files** (not DEVNULL) to preserve debugging
- **PULSE_SERVER environment variable preserved** for audio connectivity
- Web apps can still access PulseAudio at tcp:127.0.0.1:4713

### 3. Safe Process Termination
- PID verification before killing processes
- Checks command line for audio-related keywords
- Refuses to terminate processes with audio signatures
- Uses process groups for clean shutdown

### 4. Audio Service Protection Module
- `audio_protection.py` monitors and protects audio services
- Tracks protected PIDs
- Health checking and diagnostics
- Automatic restart capability

### 5. Audio Capability Preservation
- **Environment inheritance**: PULSE_SERVER passed to subprocesses
- **Log files instead of DEVNULL**: Preserves output while avoiding competition
- **Web Audio API support**: Browser can connect to PulseAudio
- **Backend audio access**: Flask/Python can use pactl, paplay, etc.

## Key Files Modified

1. **web_deployment.py**
   - Added reserved port list
   - Implemented process isolation
   - Safe termination with PID verification
   - Process group management

2. **language_executor.py**
   - Updated port selection to avoid audio ports
   - Added process isolation
   - Platform-specific subprocess handling

3. **audio_protection.py** (NEW)
   - Audio service scanner
   - Health monitoring
   - Process protection
   - Port conflict detection

## Usage

### Check Audio Health
```python
from claude_agent.core.audio_protection import check_audio_health
print(check_audio_health())
```

### Deploy Web App Safely
```python
from claude_agent.core.web_deployment import WebDeploymentManager
manager = WebDeploymentManager()
result = manager.deploy_web_app(html_content="<h1>Test</h1>")
# Automatically avoids audio ports
```

### Protect Audio Services
```python
from claude_agent.core.audio_protection import protect_audio_services
protect_audio_services()  # Marks all audio PIDs as protected
```

## Testing

Run the test suite:
```bash
python3 test_audio_safety.py
```

This verifies:
- Audio ports are avoided
- Process isolation works
- Safe cleanup doesn't affect audio
- Multiple deployments don't interfere

## NetHunter-Specific Considerations

The solution is optimized for NetHunter environments where:
- PulseAudio runs over TCP (port 4713)
- Audio warmstart scripts run in background
- KEX audio bridge is active
- ADB port forwarding is used

## Monitoring

The system now logs:
- Port selection decisions
- Process group creation
- Cleanup operations
- Audio service health

Check logs for diagnostics:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Future Improvements

1. Automatic audio service recovery
2. Real-time port monitoring
3. Process priority management
4. Audio latency optimization

## Summary

This solution ensures web app deployments never interfere with audio services by:
- **Preventing** port conflicts through reservation
- **Isolating** processes in separate groups
- **Protecting** audio PIDs from termination
- **Monitoring** service health continuously

The implementation is robust, platform-aware, and handles edge cases gracefully.