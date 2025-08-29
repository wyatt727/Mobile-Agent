# Mobile Agent 🤖

An AI-powered command execution agent for NetHunter and MacOS. Control your Android device, launch apps, create websites, and perform security operations using natural language.

## Features

### NetHunter/Android
- **App Control**: Launch any Android app by name
- **Web Development**: Auto-deploy websites with single HTML block
- **Security Tools**: Integrated with NetHunter toolkit
- **System Control**: Screenshots, file management, monitoring
- **Browser Automation**: Open websites, perform searches

### MacOS
- **Playwright Automation**: Browser control and scraping  
- **System Automation**: AppleScript integration
- **File Operations**: Advanced file management

## Quick Start

```bash
# Clone and install
git clone https://github.com/wyatt727/Mobile-Agent.git
cd Mobile-Agent
./install-mobile.sh

# Use the agent
agent create a simple web page
```

## Installation

The installer automatically:
- Detects your environment (NetHunter/MacOS)
- Sets up Python virtual environment
- Installs all dependencies
- Creates system-wide `agent` command

### NetHunter
Installs to `/root/.mobile-agent/` - self-contained, can delete source.

### MacOS  
Runs from installation directory - keep source files.

## How It Works

The agent uses specialized prompts based on your environment:
- **NetHunter**: Full Android control via ADB
- **MacOS**: Playwright browser automation
- **Web**: Auto-deployment with Python server

## Examples

```bash
# Android control
agent open telegram
agent install app.apk
agent check battery status

# Web development
agent create a game with touch controls
agent build a react dashboard
agent make a portfolio website

# Security
agent scan example.com
agent monitor network traffic
agent check system security

# Automation
agent search for Python tutorials
agent take a screenshot and pull it
agent open calculator
```

## Requirements

- Python 3.6+
- NetHunter: ADB tools
- MacOS: Playwright support

## Architecture

```
Mobile-Agent/
├── agent                   # Main executable
├── claude_agent/           # Core modules
│   ├── core/              # Execution engine
│   └── prompt/            # System prompts
└── install-mobile.sh      # Universal installer
```

## License

MIT License - Use freely!

## Contributing

Pull requests welcome! Please test on both NetHunter and MacOS.

## Support

- Issues: [GitHub Issues](https://github.com/yourusername/Mobile-Agent/issues)
- Wiki: [Documentation](https://github.com/yourusername/Mobile-Agent/wiki)

---

**Made with ❤️ for the NetHunter community**