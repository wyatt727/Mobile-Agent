"""Utility functions and models for Claude Agent"""

from claude_agent.utils.models import (
    MessageRole,
    CodeLanguage,
    Message,
    ExecutionResult,
    CodeBlock,
    ConversationStats
)

from claude_agent.utils.helpers import (
    setup_logging,
    load_config_file,
    print_colored,
    format_execution_result,
    validate_environment,
    print_environment_status,
    create_default_files
)

__all__ = [
    # Models
    "MessageRole",
    "CodeLanguage",
    "Message",
    "ExecutionResult",
    "CodeBlock",
    "ConversationStats",
    # Helpers
    "setup_logging",
    "load_config_file",
    "print_colored",
    "format_execution_result",
    "validate_environment",
    "print_environment_status",
    "create_default_files"
]