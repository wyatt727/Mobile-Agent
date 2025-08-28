#!/usr/bin/env python3
"""
Helper utilities for Claude Agent
"""
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
try:
    import yaml
except ImportError:
    yaml = None


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        format_string: Optional custom format string
        
    Returns:
        Root logger
    """
    # Default format
    if not format_string:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string
    )
    
    # Get root logger
    logger = logging.getLogger()
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(format_string))
        logger.addHandler(file_handler)
    
    return logger


def load_config_file(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from JSON or YAML file.
    
    Args:
        file_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        if path.suffix.lower() in ['.yml', '.yaml']:
            if yaml:
                return yaml.safe_load(f)
            else:
                raise ImportError("PyYAML is not installed. Use JSON config or install with: pip install pyyaml")
        else:
            return json.load(f)


def print_colored(text: str, color: str = "default", bold: bool = False):
    """
    Print colored text to terminal.
    
    Args:
        text: Text to print
        color: Color name (red, green, yellow, blue, magenta, cyan)
        bold: Whether to print in bold
    """
    colors = {
        "default": "",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m"
    }
    
    reset = "\033[0m"
    bold_code = "\033[1m" if bold else ""
    
    color_code = colors.get(color, "")
    print(f"{bold_code}{color_code}{text}{reset}")


def format_execution_result(result, verbose: bool = False) -> str:
    """
    Format execution result for display.
    
    Args:
        result: ExecutionResult object
        verbose: Whether to include detailed information
        
    Returns:
        Formatted string
    """
    from claude_agent.utils.models import ExecutionResult
    
    if not isinstance(result, ExecutionResult):
        return str(result)
    
    lines = []
    
    # Status indicator
    status = "✓" if result.success else "✗"
    color = "green" if result.success else "red"
    
    lines.append(f"{status} {result.language.upper()} Execution")
    
    if verbose:
        lines.append(f"  Return code: {result.return_code}")
        lines.append(f"  Execution time: {result.execution_time:.2f}s")
        if result.timeout:
            lines.append("  Status: TIMEOUT")
    
    # Output
    if result.output:
        lines.append("Output:")
        for line in result.output.split('\n'):
            lines.append(f"  {line}")
    
    # Error
    if result.error:
        lines.append("Error:")
        for line in result.error.split('\n'):
            lines.append(f"  {line}")
    
    return "\n".join(lines)


def validate_environment() -> Dict[str, bool]:
    """
    Validate the environment for running Claude Agent.
    
    Returns:
        Dictionary of component availability
    """
    import subprocess
    
    checks = {}
    
    # Check Python version
    checks['python_version'] = sys.version_info >= (3, 8)
    
    # Check Claude CLI (try custom path first, then fallback to PATH)
    claude_paths = ["/usr/local/bin/claude", "claude"]
    checks['claude_cli'] = False
    
    for claude_path in claude_paths:
        try:
            # Check if it's a file path that exists
            if "/" in claude_path:
                from pathlib import Path
                if not Path(claude_path).exists():
                    continue
            
            result = subprocess.run(
                [claude_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                checks['claude_cli'] = True
                break
        except:
            continue
    
    # Check Node.js (for JavaScript execution)
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        checks['nodejs'] = result.returncode == 0
    except:
        checks['nodejs'] = False
    
    # Check pip
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        checks['pip'] = result.returncode == 0
    except:
        checks['pip'] = False
    
    # Check Ollama (fallback LLM)
    try:
        import requests
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        checks['ollama'] = response.status_code == 200
    except:
        checks['ollama'] = False
    
    return checks


def print_environment_status():
    """Print environment validation status."""
    print("\n=== Environment Status ===\n")
    
    checks = validate_environment()
    
    for component, available in checks.items():
        status = "✓" if available else "✗"
        color = "green" if available else "yellow"
        display_name = component.replace('_', ' ').title()
        print_colored(f"{status} {display_name}", color)
    
    # Determine overall status
    critical = ['python_version', 'pip']
    critical_ok = all(checks[c] for c in critical)
    
    llm_ok = checks['claude_cli'] or checks['ollama']
    
    print("\n=== Summary ===\n")
    
    if not critical_ok:
        print_colored("Critical components missing. Agent cannot run.", "red", bold=True)
    elif not llm_ok:
        print_colored("No LLM provider available. Please install Claude CLI or Ollama.", "yellow", bold=True)
    else:
        print_colored("Environment ready!", "green", bold=True)
        if not checks['claude_cli']:
            print_colored("Note: Claude CLI not available, using fallback LLM", "yellow")
        if not checks['nodejs']:
            print_colored("Note: Node.js not available, JavaScript execution disabled", "yellow")
    
    print()


def create_default_files(directory: str = "."):
    """
    Create default configuration and prompt files.
    
    Args:
        directory: Directory to create files in
    """
    dir_path = Path(directory)
    dir_path.mkdir(parents=True, exist_ok=True)
    
    # Default system prompt
    system_prompt = """You are a helpful AI assistant that can write and execute code.
When you provide code, wrap it in appropriate code blocks with the language specified.
For example:
```python
print("Hello, World!")
```

You can execute Python, shell scripts, and JavaScript code.
Always strive to provide working, efficient, and well-structured code."""
    
    system_prompt_file = dir_path / "system_prompt.txt"
    if not system_prompt_file.exists():
        with open(system_prompt_file, 'w', encoding='utf-8') as f:
            f.write(system_prompt)
        print(f"Created default system prompt: {system_prompt_file}")
    
    # Default configuration
    default_config = {
        "claude_model": "sonnet",
        "execution_timeout": 60,
        "max_fix_attempts": 3,
        "max_history_length": 100,
        "auto_install_packages": True,
        "save_code_files": True,
        "verbose": False
    }
    
    config_file = dir_path / "claude_agent_config.json"
    if not config_file.exists():
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2)
        print(f"Created default configuration: {config_file}")
    
    # Create .gitignore
    gitignore_content = """# Claude Agent
conversation.json
generated_code/
*.log
.env
__pycache__/
*.pyc
"""
    
    gitignore_file = dir_path / ".gitignore"
    if not gitignore_file.exists():
        with open(gitignore_file, 'w') as f:
            f.write(gitignore_content)
        print(f"Created .gitignore: {gitignore_file}")