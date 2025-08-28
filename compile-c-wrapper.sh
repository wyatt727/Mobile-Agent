#!/bin/sh
# Compile the C wrapper for agent execution

echo "🔧 Investigating shell situation and compiling C wrapper..."

# First, investigate the shell situation
echo "🔍 Shell investigation:"
echo "  /bin/sh -> $(ls -l /bin/sh 2>/dev/null || echo 'not found')"
echo "  /bin/bash -> $(ls -l /bin/bash 2>/dev/null || echo 'not found')"  
echo "  /bin/dash -> $(ls -l /bin/dash 2>/dev/null || echo 'not found')"
echo "  busybox -> $(which busybox 2>/dev/null || echo 'not found')"
echo ""

echo "🔧 Compiling C wrapper with multiple approaches..."

# Try different compilation approaches
SUCCESS=0

# Approach 1: Standard gcc
echo "Trying: gcc -o agent-noshrc agent-noshrc.c"
if gcc -o agent-noshrc agent-noshrc.c 2>/dev/null; then
    SUCCESS=1
    echo "✅ Standard gcc compilation succeeded"
fi

# Approach 2: Static linking
if [ $SUCCESS -eq 0 ]; then
    echo "Trying: gcc -static -o agent-noshrc agent-noshrc.c"
    if gcc -static -o agent-noshrc agent-noshrc.c 2>/dev/null; then
        SUCCESS=1
        echo "✅ Static linking compilation succeeded"
    fi
fi

# Approach 3: Different compiler
if [ $SUCCESS -eq 0 ] && command -v clang >/dev/null 2>&1; then
    echo "Trying: clang -o agent-noshrc agent-noshrc.c"
    if clang -o agent-noshrc agent-noshrc.c 2>/dev/null; then
        SUCCESS=1
        echo "✅ Clang compilation succeeded"
    fi
fi

# Approach 4: Cross-compile for ARM64
if [ $SUCCESS -eq 0 ] && command -v aarch64-linux-gnu-gcc >/dev/null 2>&1; then
    echo "Trying: aarch64-linux-gnu-gcc -static -o agent-noshrc agent-noshrc.c"
    if aarch64-linux-gnu-gcc -static -o agent-noshrc agent-noshrc.c 2>/dev/null; then
        SUCCESS=1
        echo "✅ ARM64 cross-compilation succeeded"
    fi
fi

if [ $SUCCESS -eq 1 ]; then
    chmod +x agent-noshrc
    echo "✅ C wrapper compiled successfully: agent-noshrc"
    ls -la agent-noshrc
    file agent-noshrc 2>/dev/null || echo "file command not available"
else
    echo "❌ All compilation attempts failed"
    echo "Available compilers:"
    for compiler in gcc clang cc aarch64-linux-gnu-gcc; do
        if command -v $compiler >/dev/null 2>&1; then
            echo "  ✓ $compiler"
        else
            echo "  ✗ $compiler"
        fi
    done
    exit 1
fi