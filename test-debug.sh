#!/bin/bash
# Test script to run agent with subprocess debugging enabled

echo "🔍 Mobile Agent Shell Bypass Testing"
echo "=================================="
echo "🔍 Current SHELL: $SHELL"
echo "🔍 Current shell process: $(readlink -f /proc/$$/exe 2>/dev/null || echo 'unknown')"
echo ""

# Investigate shell situation first
echo "🔍 Shell Investigation:"
make debug-shells 2>/dev/null || ./compile-c-wrapper.sh | head -15
echo ""

# Test 1: Regular agent (this loads .zshrc)
echo "🔍 Test 1: Regular agent (loads .zshrc - SHOULD OPEN TERMUX)..."
echo "   Command: /root/.mobile-agent/agent"
env AGENT_DEBUG_SUBPROCESS=1 /root/.mobile-agent/agent "create a simple html page"

echo ""
echo "🔍 Test 2: /bin/sh wrapper (may still load .zshrc if sh->zsh)..."
echo "   Command: ./agent-noshell"
env AGENT_DEBUG_SUBPROCESS=1 ./agent-noshell "create a simple html page"

echo ""
echo "🔍 Test 3: Busybox sh wrapper (should NOT load .zshrc)..."
chmod +x ./agent-busybox 2>/dev/null
if command -v busybox >/dev/null 2>&1; then
    echo "   Command: ./agent-busybox"
    env AGENT_DEBUG_SUBPROCESS=1 ./agent-busybox "create a simple html page"
else
    echo "   ❌ Busybox not available"
fi

echo ""
echo "🔍 Test 4: C wrapper (completely bypasses shell)..."
# Try compiling C wrapper
if [ ! -f ./agent-noshrc ]; then
    echo "   Compiling C wrapper..."
    if make agent-noshrc 2>/dev/null; then
        echo "   ✅ Make compilation succeeded"
    elif ./compile-c-wrapper.sh 2>/dev/null; then
        echo "   ✅ Script compilation succeeded"
    else
        echo "   ⚠️  Trying manual compilation..."
        gcc -o agent-noshrc agent-noshrc.c 2>/dev/null || \
        gcc -static -o agent-noshrc agent-noshrc.c 2>/dev/null || \
        clang -o agent-noshrc agent-noshrc.c 2>/dev/null || \
        echo "   ❌ All compilation attempts failed"
    fi
fi

if [ -f ./agent-noshrc ]; then
    echo "   Command: ./agent-noshrc"
    env AGENT_DEBUG_SUBPROCESS=1 ./agent-noshrc "create a simple html page"
else
    echo "   ❌ C wrapper not available"
fi

echo ""
echo "🔍 SUMMARY:"
echo "   If ANY test above did NOT open Termux, that's your solution!"
echo "   Update /usr/local/bin/agent symlink to point to the working method."