#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>

/*
 * C wrapper that completely bypasses shell initialization
 * This CANNOT load .zshrc because it uses execv() directly
 * Compiled for ARM64 architecture on NetHunter
 */

int main(int argc, char *argv[]) {
    // Handle --help option for testing
    if (argc > 1 && strcmp(argv[1], "--help") == 0) {
        printf("Mobile Agent C Wrapper (ARM64)\n");
        printf("Prevents .zshrc loading by using execve() directly\n");
        printf("Usage: %s <agent-request>\n", argv[0]);
        return 0;
    }
    
    fprintf(stderr, "🔍 C WRAPPER (ARM64): Starting with %d args\n", argc);
    
    // Prepare arguments for the real agent
    char *agent_args[argc + 2];
    agent_args[0] = "/root/.mobile-agent/.claude_venv/bin/python";
    agent_args[1] = "/root/.mobile-agent/agent";
    
    // Copy user arguments
    for (int i = 1; i < argc; i++) {
        agent_args[i + 1] = argv[i];
        fprintf(stderr, "🔍 C WRAPPER: Arg %d: %s\n", i, argv[i]);
    }
    agent_args[argc + 1] = NULL;
    
    // Set up minimal environment
    char *clean_env[] = {
        "PATH=/usr/bin:/bin:/usr/local/bin:/sbin:/usr/sbin",
        "PYTHONPATH=/root/.mobile-agent",
        "PYTHONIOENCODING=utf-8",
        "PYTHONNOUSERSITE=1", 
        "PYTHONDONTWRITEBYTECODE=1",
        NULL
    };
    
    // Add debug flag if present in original environment
    char *debug_flag = getenv("AGENT_DEBUG_SUBPROCESS");
    if (debug_flag && strcmp(debug_flag, "1") == 0) {
        fprintf(stderr, "🔍 C WRAPPER: Adding debug flag\n");
        // Extend clean_env array to include debug flag
        static char *clean_env_debug[] = {
            "PATH=/usr/bin:/bin:/usr/local/bin:/sbin:/usr/sbin",
            "PYTHONPATH=/root/.mobile-agent", 
            "PYTHONIOENCODING=utf-8",
            "PYTHONNOUSERSITE=1",
            "PYTHONDONTWRITEBYTECODE=1",
            "AGENT_DEBUG_SUBPROCESS=1",
            NULL
        };
        clean_env = clean_env_debug;
    }
    
    fprintf(stderr, "🔍 C WRAPPER: Executing with clean environment\n");
    
    // Execute the real agent with completely clean environment
    // This is guaranteed to NOT load any shell initialization files
    execve("/root/.mobile-agent/.claude_venv/bin/python", agent_args, clean_env);
    
    // If we get here, execve failed
    perror("🔍 C WRAPPER: execve failed");
    return 1;
}