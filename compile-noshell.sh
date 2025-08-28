#!/bin/bash
# Compile the no-shell C wrapper for NetHunter

echo "Compiling agent-noshell C wrapper..."

# Update paths in the C file for NetHunter
INSTALL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create a temporary C file with correct paths
cat > /tmp/agent-noshell-tmp.c << EOF
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: agent-noshell <request>\\n");
        return 1;
    }
    
    // Clear environment completely
    clearenv();
    
    // Set minimal environment
    setenv("PATH", "/usr/bin:/bin:/usr/local/bin:/usr/sbin:/sbin", 1);
    setenv("PYTHONIOENCODING", "utf-8", 1);
    setenv("PYTHONPATH", "${INSTALL_DIR}", 1);
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);
    setenv("PYTHONNOUSERSITE", "1", 1);
    setenv("PYTHONUNBUFFERED", "1", 1);
    
    // NetHunter mode
    setenv("NETHUNTER_MODE", "1", 1);
    
    // Build argv for Python
    char *python_argv[1024];
    python_argv[0] = "/usr/bin/python3";
    python_argv[1] = "-E";  // Ignore environment
    python_argv[2] = "-s";  // No user site
    python_argv[3] = "-u";  // Unbuffered
    python_argv[4] = "${INSTALL_DIR}/agent-direct";
    
    // Copy user arguments
    int i;
    for (i = 1; i < argc && i < 1019; i++) {
        python_argv[i + 4] = argv[i];
    }
    python_argv[i + 4] = NULL;
    
    // Execute Python directly with execv (no shell involved)
    execv("/usr/bin/python3", python_argv);
    
    // If we get here, exec failed
    perror("Failed to execute Python");
    return 1;
}
EOF

# Compile
gcc -O2 -o agent-noshell /tmp/agent-noshell-tmp.c

if [ $? -eq 0 ]; then
    echo "✓ Compiled successfully: agent-noshell"
    echo ""
    echo "To use the no-shell wrapper:"
    echo "  ./agent-noshell 'your request here'"
    echo ""
    echo "Or install system-wide:"
    echo "  sudo cp agent-noshell /usr/local/bin/"
    echo "  sudo chmod +x /usr/local/bin/agent-noshell"
else
    echo "✗ Compilation failed"
    echo "Make sure gcc is installed: apt-get install gcc"
fi

rm -f /tmp/agent-noshell-tmp.c