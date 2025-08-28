#!/bin/bash
# Test script to run agent with subprocess debugging enabled

echo "🔍 Testing agent with subprocess debugging..."
echo "🔍 Current SHELL: $SHELL"
echo "🔍 This will show ALL subprocess calls and their environments"
echo ""

# Enable debugging and run a simple command
export AGENT_DEBUG_SUBPROCESS=1
/usr/local/bin/agent "create a simple html page"