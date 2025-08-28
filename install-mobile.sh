#!/bin/bash
# Mobile Agent Installation Script - Optimized for NetHunter and MacOS
# NetHunter: Installs to /root/.mobile-agent
# MacOS: Installs in place with symlink

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Mobile Agent Installation v3.0     ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo

# Detect environment
detect_environment() {
    if [ -f /etc/nethunter ] || [ -d /data/local/nhsystem ] || [ -f /root/.nethunter ]; then
        echo "nethunter"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [ -n "$ANDROID_ROOT" ] || [ -f /system/build.prop ]; then
        echo "android"
    else
        echo "linux"
    fi
}

ENV_TYPE=$(detect_environment)
echo -e "${BLUE}[*]${NC} Environment detected: ${GREEN}$ENV_TYPE${NC}"

# Get source directory (where the repo was cloned)
SOURCE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Determine installation paths based on environment
case "$ENV_TYPE" in
    nethunter|android)
        # NetHunter: Install to /root/.mobile-agent for cleaner organization
        INSTALL_BASE="/root/.mobile-agent"
        BIN_DIR="/usr/local/bin"  # You confirmed this is writable
        SHELL_CONFIG="/root/.bashrc"
        COPY_FILES=true  # Copy files to installation directory
        ;;
    macos)
        # MacOS: Use current directory, just create symlink
        INSTALL_BASE="$SOURCE_DIR"
        BIN_DIR="/usr/local/bin"
        SHELL_CONFIG="$HOME/.zshrc"
        [ ! -f "$SHELL_CONFIG" ] && SHELL_CONFIG="$HOME/.bash_profile"
        COPY_FILES=false  # Don't copy, use in place
        ;;
    *)
        # Generic Linux
        INSTALL_BASE="$HOME/.mobile-agent"
        BIN_DIR="$HOME/.local/bin"
        mkdir -p "$BIN_DIR"
        SHELL_CONFIG="$HOME/.bashrc"
        COPY_FILES=true
        ;;
esac

echo -e "${BLUE}[*]${NC} Installation directory: ${GREEN}$INSTALL_BASE${NC}"
echo -e "${BLUE}[*]${NC} Binary directory: ${GREEN}$BIN_DIR${NC}"

# Check Python
echo -e "\n${BLUE}[*]${NC} Checking Python installation..."
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo -e "${RED}[!] Python not found!${NC}"
    case "$ENV_TYPE" in
        nethunter|android)
            echo "    Run: apt update && apt install -y python3 python3-pip python3-venv"
            ;;
        macos)
            echo "    Run: brew install python3"
            ;;
    esac
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}[✓]${NC} Found Python $PYTHON_VERSION"

# Copy files if needed (NetHunter installation)
if [ "$COPY_FILES" = true ] && [ "$SOURCE_DIR" != "$INSTALL_BASE" ]; then
    echo -e "\n${BLUE}[*]${NC} Copying files to $INSTALL_BASE..."
    
    # Backup existing installation if present
    if [ -d "$INSTALL_BASE" ]; then
        BACKUP_DIR="${INSTALL_BASE}.backup.$(date +%Y%m%d_%H%M%S)"
        echo -e "${YELLOW}[*]${NC} Backing up existing installation to $BACKUP_DIR"
        mv "$INSTALL_BASE" "$BACKUP_DIR"
    fi
    
    # Create installation directory and copy files
    mkdir -p "$INSTALL_BASE"
    cp -r "$SOURCE_DIR"/* "$INSTALL_BASE/" 2>/dev/null || {
        echo -e "${YELLOW}[*]${NC} Using rsync for better copy..."
        rsync -av --exclude='.git' --exclude='__pycache__' --exclude='.DS_Store' \
              "$SOURCE_DIR/" "$INSTALL_BASE/"
    }
    echo -e "${GREEN}[✓]${NC} Files copied to $INSTALL_BASE"
    
    # Now work from installation directory
    WORKING_DIR="$INSTALL_BASE"
else
    WORKING_DIR="$SOURCE_DIR"
fi

# Setup virtual environment
VENV_DIR="$WORKING_DIR/.claude_venv"
echo -e "\n${BLUE}[*]${NC} Setting up Python virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_CMD -m venv "$VENV_DIR" 2>/dev/null || {
        echo -e "${YELLOW}[*]${NC} Installing python3-venv..."
        case "$ENV_TYPE" in
            nethunter|android)
                apt-get update && apt-get install -y python3-venv
                ;;
            *)
                $PYTHON_CMD -m pip install --user virtualenv
                $PYTHON_CMD -m virtualenv "$VENV_DIR"
                ;;
        esac
        $PYTHON_CMD -m venv "$VENV_DIR"
    }
    echo -e "${GREEN}[✓]${NC} Virtual environment created"
else
    echo -e "${GREEN}[✓]${NC} Virtual environment exists"
fi

# Install dependencies
echo -e "\n${BLUE}[*]${NC} Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$WORKING_DIR/claude_agent/requirements.txt"
echo -e "${GREEN}[✓]${NC} Dependencies installed"

# Environment-specific setup
case "$ENV_TYPE" in
    nethunter|android)
        echo -e "\n${BLUE}[*]${NC} NetHunter setup..."
        
        # Check ADB
        if command -v adb >/dev/null 2>&1; then
            echo -e "${GREEN}[✓]${NC} ADB is available"
            
            # Try to start ADB server
            adb start-server 2>/dev/null || true
            
            # Check for connected devices
            if adb devices | grep -q "device$"; then
                echo -e "${GREEN}[✓]${NC} Android device connected"
            else
                echo -e "${YELLOW}[*]${NC} No device connected - run 'adb devices' to check"
            fi
        else
            echo -e "${YELLOW}[!]${NC} ADB not found - install with: apt install android-tools-adb"
        fi
        
        # Set NetHunter mode environment variable
        echo "export NETHUNTER_MODE=1" >> "$SHELL_CONFIG" 2>/dev/null || true
        
        # Mark as NetHunter installation
        touch "$VENV_DIR/.nethunter_installed"
        ;;
        
    macos)
        echo -e "\n${BLUE}[*]${NC} MacOS setup..."
        
        # Install Playwright browsers
        echo -e "${BLUE}[*]${NC} Installing Playwright browsers..."
        "$VENV_DIR/bin/python" -m playwright install chromium 2>/dev/null || {
            echo -e "${YELLOW}[*]${NC} Playwright installation skipped (optional)"
        }
        touch "$VENV_DIR/.playwright_installed"
        ;;
esac

# Create marker file
touch "$VENV_DIR/.requirements_installed"

# Make agent executable
chmod +x "$WORKING_DIR/agent"
chmod +x "$WORKING_DIR/agent-noshell"

# Try to find the best shell bypass method
echo -e "\n${BLUE}[*]${NC} Finding best shell bypass method..."
chmod +x "$WORKING_DIR/agent-noshell"
chmod +x "$WORKING_DIR/agent-busybox" 2>/dev/null

# Try C wrapper compilation
BYPASS_AGENT=""
if command -v gcc >/dev/null 2>&1 || command -v clang >/dev/null 2>&1 || command -v make >/dev/null 2>&1; then
    cd "$WORKING_DIR"
    
    # Try make first
    if make agent-noshrc >/dev/null 2>&1; then
        BYPASS_AGENT="$WORKING_DIR/agent-noshrc"
        echo -e "${GREEN}[✓]${NC} C wrapper compiled with make (complete shell bypass)"
    # Try direct gcc compilation
    elif gcc -o agent-noshrc agent-noshrc.c 2>/dev/null; then
        chmod +x agent-noshrc
        BYPASS_AGENT="$WORKING_DIR/agent-noshrc" 
        echo -e "${GREEN}[✓]${NC} C wrapper compiled with gcc (complete shell bypass)"
    # Try static linking
    elif gcc -static -o agent-noshrc agent-noshrc.c 2>/dev/null; then
        chmod +x agent-noshrc
        BYPASS_AGENT="$WORKING_DIR/agent-noshrc"
        echo -e "${GREEN}[✓]${NC} C wrapper compiled static (complete shell bypass)"
    # Try clang
    elif clang -o agent-noshrc agent-noshrc.c 2>/dev/null; then
        chmod +x agent-noshrc
        BYPASS_AGENT="$WORKING_DIR/agent-noshrc"
        echo -e "${GREEN}[✓]${NC} C wrapper compiled with clang (complete shell bypass)"
    fi
fi

# Fallback to shell wrappers
if [ -z "$BYPASS_AGENT" ]; then
    # Check if busybox is available and sh is linked to zsh
    if command -v busybox >/dev/null 2>&1 && [ "$(readlink /bin/sh | grep -c zsh)" -gt 0 ] 2>/dev/null; then
        BYPASS_AGENT="$WORKING_DIR/agent-busybox"
        echo -e "${YELLOW}[*]${NC} C compilation failed, using busybox sh wrapper (sh is zsh)"
    else
        BYPASS_AGENT="$WORKING_DIR/agent-noshell"
        echo -e "${YELLOW}[*]${NC} C compilation failed, using /bin/sh wrapper"
    fi
fi

# Create symlink to best available shell-bypassing agent
echo -e "\n${BLUE}[*]${NC} Creating symlink..."
ln -sf "$BYPASS_AGENT" "$BIN_DIR/agent"
echo -e "${GREEN}[✓]${NC} Symlink created: ${CYAN}$BIN_DIR/agent${NC} → ${CYAN}$BYPASS_AGENT${NC}"
echo -e "   This prevents .zshrc loading and Termux auto-start"

# Update PATH if needed
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "\n${YELLOW}[*]${NC} Adding $BIN_DIR to PATH..."
    echo "" >> "$SHELL_CONFIG"
    echo "# Mobile Agent" >> "$SHELL_CONFIG"
    echo "export PATH=\"\$PATH:$BIN_DIR\"" >> "$SHELL_CONFIG"
    
    echo -e "${GREEN}[✓]${NC} PATH updated in $SHELL_CONFIG"
    echo -e "${YELLOW}[*]${NC} Run: ${CYAN}source $SHELL_CONFIG${NC}"
else
    echo -e "${GREEN}[✓]${NC} $BIN_DIR already in PATH"
fi

# Success message
echo
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║      Installation Successful! 🎉       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo

# Show configuration
echo -e "${CYAN}Configuration:${NC}"
echo -e "  Environment:  $ENV_TYPE"
echo -e "  Install path: $INSTALL_BASE"
echo -e "  Binary:       $BIN_DIR/agent"
echo -e "  Python:       $PYTHON_CMD ($PYTHON_VERSION)"

# NetHunter-specific note about self-contained installation
if [ "$ENV_TYPE" = "nethunter" ] || [ "$ENV_TYPE" = "android" ]; then
    echo -e "\n${GREEN}Note:${NC} Installation is self-contained in $INSTALL_BASE"
    echo -e "      You can safely delete the original cloned repository."
fi

# Show examples based on environment
echo -e "\n${CYAN}Example commands:${NC}"
case "$ENV_TYPE" in
    nethunter|android)
        echo "  agent open whatsapp"
        echo "  agent take a screenshot"
        echo "  agent scan target.com"
        echo "  agent create a react website"
        echo "  agent check system status"
        ;;
    macos)
        echo "  agent open calculator"
        echo "  agent search for Python tutorials"
        echo "  agent create a website"
        echo "  agent analyze this CSV file"
        ;;
esac

echo -e "\n${CYAN}Next steps:${NC}"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "  1. Run: ${YELLOW}source $SHELL_CONFIG${NC}"
    echo -e "  2. Test: ${YELLOW}agent --version${NC}"
else
    echo -e "  Test: ${YELLOW}agent --version${NC}"
fi

echo -e "\n${GREEN}Ready to use Mobile Agent!${NC}"