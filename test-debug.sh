#!/bin/bash
# Test script to run agent with subprocess debugging enabled

echo "🔍 Testing agent with subprocess debugging..."
echo "🔍 Current SHELL: $SHELL"
echo "🔍 This will show ALL subprocess calls and their environments"
echo ""

# Test 1: Regular agent (this loads .zshrc)
echo "🔍 Test 1: Regular agent (loads .zshrc - SHOULD OPEN TERMUX)..."
env AGENT_DEBUG_SUBPROCESS=1 /root/.mobile-agent/agent "create a simple html page"

echo ""
echo "🔍 Test 2: /bin/sh wrapper (should NOT load .zshrc)..."
# Test 2: /bin/sh wrapper
env AGENT_DEBUG_SUBPROCESS=1 ./agent-noshell "create a simple html page"

echo ""
echo "🔍 Test 3: C wrapper (completely bypasses shell)..."
# Test 3: C wrapper - compile if needed
if [ ! -f ./agent-noshrc ]; then
    echo "   Compiling C wrapper..."
    ./compile-c-wrapper.sh
fi
if [ -f ./agent-noshrc ]; then
    env AGENT_DEBUG_SUBPROCESS=1 ./agent-noshrc "create a simple html page"
else
    echo "   ❌ C wrapper not available"
fi