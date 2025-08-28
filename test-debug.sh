#!/bin/bash
# Test script to run agent with subprocess debugging enabled

echo "🔍 Testing agent with subprocess debugging..."
echo "🔍 Current SHELL: $SHELL"
echo "🔍 This will show ALL subprocess calls and their environments"
echo ""

# Enable debugging and run a simple command with explicit environment
echo "🔍 Setting AGENT_DEBUG_SUBPROCESS=1 and running agent..."
env AGENT_DEBUG_SUBPROCESS=1 /usr/local/bin/agent "create a simple html page"