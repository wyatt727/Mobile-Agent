#!/usr/bin/env python3
"""
Demonstration of the improved fix prompt structure
"""

def demonstrate_improved_fix_prompt():
    """Show what the new fix prompt looks like"""
    
    original_request = "Create a website that shows the current time and updates every second"
    failed_code = """<!DOCTYPE html>
<html>
<head><title>Time</title></head>
<body>
    <div id="time"></div>
    <script>
        document.getElementByID('time').innerText = new Date();
    </script>
</body>
</html>"""
    
    error_output = "Uncaught TypeError: document.getElementByID is not a function"
    stdout = ""
    return_code = 1
    execution_time = 0.5
    error_file_path = "/tmp/12345_errors.txt"
    
    print("=== IMPROVED FIX PROMPT STRUCTURE ===\n")
    print("IMPORTANT CONTEXT: You are operating within a NetHunter chroot environment.")
    print("\nPlease read and follow these system prompts for proper execution:")
    print("@claude_agent/prompt/nethunter-system-prompt-v3.md")
    print("@claude_agent/prompt/WebDev_Claude.md")
    print()
    print("=== ORIGINAL USER REQUEST ===")
    print(original_request)
    print()
    print("=== WHAT WAS ATTEMPTED ===")
    print("The following html code was generated and executed:")
    print()
    print("    " + failed_code.replace('\n', '\n    '))
    print()
    print("=== COMPLETE ERROR OUTPUT ===")
    print("The execution failed with the following output:")
    print()
    print("STDOUT:")
    print("(no stdout output)" if not stdout else stdout)
    print()
    print("STDERR:")
    print(error_output)
    print()
    print(f"Return code: {return_code}")
    print(f"Execution time: {execution_time}s")
    print()
    print("=== ERROR HISTORY AVAILABLE ===")
    print(f"IMPORTANT: For complete context of all previous attempts, please read: @{error_file_path}")
    print()
    print("This file contains:")
    print("- All previous execution attempts with full output")
    print("- Previous fix attempts and Claude's responses")
    print("- Detailed execution timing for each attempt")
    print("- Progressive context showing what has been tried")
    print()
    print("=== YOUR TASK ===")
    print("Please analyze the error and provide a solution. You may either:")
    print("1. Fix the existing code if the approach is sound")
    print("2. Try a completely different approach to achieve the user's goal")
    print()
    print("Remember to follow the NetHunter system prompt rules.")
    print("Return your solution as executable html code block(s), following the language identifier rules from the system prompt.")
    print()
    print("\n" + "="*60)
    print("\nKEY IMPROVEMENTS:")
    print("1. ✅ Starts with ORIGINAL USER REQUEST - keeps focus on the goal")
    print("2. ✅ References NetHunter system prompts - preserves execution context")
    print("3. ✅ Shows code with indentation - avoids nested code block confusion")
    print("4. ✅ Shows ALL output (stdout + stderr) - complete error context")
    print("5. ✅ References error history file - cumulative retry context")
    print("6. ✅ Allows alternative approaches - not locked into fixing bad code")
    print("7. ✅ Detects web requests - includes WebDev_Claude.md when relevant")

if __name__ == "__main__":
    demonstrate_improved_fix_prompt()