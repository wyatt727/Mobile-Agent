#!/bin/sh
# Quick fix for .zshrc loading issue - bypasses shell initialization

echo "🚀 Quick Fix: Bypassing .zshrc Loading"
echo "====================================="

# Check where we are
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Working in: $SCRIPT_DIR"

# Method 1: Try ARM64 C compilation
echo ""
echo "🔧 Attempting ARM64 C wrapper compilation..."

# Install build tools if missing
if ! command -v gcc >/dev/null 2>&1; then
    echo "  Installing gcc..."
    apt update >/dev/null 2>&1
    apt install -y build-essential >/dev/null 2>&1
fi

# Try compilation with architecture detection
ARCH="$(uname -m)"
echo "  Architecture: $ARCH"

if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    # Native ARM64 compilation
    if gcc -march=armv8-a -O2 -o agent-noshrc agent-noshrc.c 2>/dev/null; then
        echo "  ✅ Native ARM64 compilation successful!"
        chmod +x agent-noshrc
        
        # Test the binary
        if ./agent-noshrc --help >/dev/null 2>&1; then
            echo "  ✅ ARM64 binary works correctly"
            echo "  🔗 Updating symlink to use C wrapper..."
            ln -sf "$SCRIPT_DIR/agent-noshrc" /usr/local/bin/agent
            echo ""
            echo "🎉 SUCCESS! C wrapper active"
            echo "   /usr/local/bin/agent -> $SCRIPT_DIR/agent-noshrc"
            echo ""
            echo "🧪 Test: agent 'test page' (should NOT open Termux)"
            exit 0
        fi
    fi
    
    # Fallback to simple gcc
    if gcc -o agent-noshrc agent-noshrc.c 2>/dev/null; then
        echo "  ✅ Standard gcc compilation successful!"
        chmod +x agent-noshrc
        if ./agent-noshrc --help >/dev/null 2>&1; then
            echo "  ✅ Binary works correctly"
            ln -sf "$SCRIPT_DIR/agent-noshrc" /usr/local/bin/agent
            echo "🎉 SUCCESS! C wrapper active"
            exit 0
        fi
    fi
fi

echo "  ❌ C compilation failed or produced non-working binary"

# Method 2: Use busybox if sh->zsh
echo ""
echo "🔧 Checking shell situation..."
if [ -L /bin/sh ]; then
    SH_TARGET="$(readlink /bin/sh)"
    echo "  /bin/sh -> $SH_TARGET"
    
    if echo "$SH_TARGET" | grep -q zsh; then
        echo "  ⚠️  /bin/sh points to zsh (will load .zshrc)"
        
        if command -v busybox >/dev/null 2>&1; then
            echo "  ✅ Busybox available - using busybox sh wrapper"
            chmod +x "$SCRIPT_DIR/agent-busybox"
            ln -sf "$SCRIPT_DIR/agent-busybox" /usr/local/bin/agent
            echo ""
            echo "🎉 SUCCESS! Busybox wrapper active"
            echo "   /usr/local/bin/agent -> $SCRIPT_DIR/agent-busybox"
            echo ""
            echo "🧪 Test: agent 'test page' (should NOT open Termux)"
            exit 0
        fi
    fi
fi

# Method 3: Standard shell wrapper
echo "  Using standard /bin/sh wrapper as fallback"
chmod +x "$SCRIPT_DIR/agent-noshell"
ln -sf "$SCRIPT_DIR/agent-noshell" /usr/local/bin/agent
echo ""
echo "⚠️  FALLBACK: Using /bin/sh wrapper"  
echo "   /usr/local/bin/agent -> $SCRIPT_DIR/agent-noshell"
echo "   This may still load .zshrc if sh->zsh"
echo ""
echo "🧪 Test: agent 'test page'"
echo "   If Termux still opens, .zshrc loading wasn't prevented"

echo ""
echo "💡 Alternative: Try running commands directly:"
echo "   $SCRIPT_DIR/agent-noshrc 'test page'      # C wrapper (if compiled)"
echo "   $SCRIPT_DIR/agent-busybox 'test page'     # Busybox wrapper"
echo "   $SCRIPT_DIR/agent-noshell 'test page'     # Shell wrapper"