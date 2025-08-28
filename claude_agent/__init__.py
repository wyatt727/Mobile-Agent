#!/usr/bin/env python3
"""
Claude Agent - AI-powered code execution agent
"""

__version__ = "2.0.0"
__author__ = "Claude Agent Team"

from claude_agent.config import AgentConfig
from claude_agent.core.claude_agent import ClaudeAgent, AgentMode
from claude_agent.core.conversation_manager import ConversationManager
from claude_agent.core.code_executor import CodeExecutor
from claude_agent.providers.claude_provider import ClaudeCodeProvider, FallbackProvider

__all__ = [
    "AgentConfig",
    "ClaudeAgent",
    "AgentMode",
    "ConversationManager",
    "CodeExecutor",
    "ClaudeCodeProvider",
    "FallbackProvider"
]