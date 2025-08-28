#!/bin/bash
# Test script to run agent with subprocess debugging enabled

echo "🔍 Testing agent with subprocess debugging..."
echo "🔍 Current SHELL: $SHELL"
echo "🔍 This will show ALL subprocess calls and their environments"
echo ""

# Test 1: Regular agent (this loads .zshrc)
echo "🔍 Test 1: Regular agent (loads .zshrc)..."
env AGENT_DEBUG_SUBPROCESS=1 /usr/local/bin/agent "create a simple html page"

echo ""
echo "🔍 Test 2: Shell-bypassing agent (should NOT load .zshrc)..."
# Test 2: Shell-bypassing agent
env AGENT_DEBUG_SUBPROCESS=1 ./agent-noshell "create a simple html page"

echo ""
echo "🔍 Test 3: Direct Python agent (completely bypasses shell)..."
# Test 3: Direct Python execution
env AGENT_DEBUG_SUBPROCESS=1 ./agent-direct.py "create a simple html page"