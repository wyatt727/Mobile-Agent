/*
 * agent-noshell: Direct Python executor that bypasses ALL shells
 * Compile with: gcc -o agent-noshell agent-noshell.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: agent-noshell <request>\n");
        return 1;
    }
    
    // Clear environment completely
    clearenv();
    
    // Set minimal environment
    setenv("PATH", "/usr/bin:/bin:/usr/local/bin", 1);
    setenv("PYTHONIOENCODING", "utf-8", 1);
    setenv("PYTHONPATH", "/root/Tools/Mobile-Agent", 1);  // Adjust path as needed
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);
    setenv("PYTHONNOUSERSITE", "1", 1);
    
    // Build argv for Python
    char *python_argv[1024];
    python_argv[0] = "/usr/bin/python3";
    python_argv[1] = "-E";  // Ignore environment
    python_argv[2] = "-s";  // No user site
    python_argv[3] = "/root/Tools/Mobile-Agent/agent-direct";  // Adjust path
    
    // Copy user arguments
    int i;
    for (i = 1; i < argc && i < 1020; i++) {
        python_argv[i + 3] = argv[i];
    }
    python_argv[i + 3] = NULL;
    
    // Execute Python directly with execv (no shell involved)
    execv("/usr/bin/python3", python_argv);
    
    // If we get here, exec failed
    perror("Failed to execute Python");
    return 1;
}