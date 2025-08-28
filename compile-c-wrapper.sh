#!/bin/sh
# Compile the C wrapper for agent execution

echo "🔧 Compiling C wrapper to prevent shell initialization..."

# Compile the C wrapper
gcc -o agent-noshrc agent-noshrc.c

if [ $? -eq 0 ]; then
    echo "✅ C wrapper compiled successfully: agent-noshrc"
    chmod +x agent-noshrc
    ls -la agent-noshrc
else
    echo "❌ C wrapper compilation failed"
    exit 1
fi