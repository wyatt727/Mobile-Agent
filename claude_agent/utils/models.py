#!/usr/bin/env python3
"""
Data models for Claude Agent
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import json


class MessageRole(Enum):
    """Roles for conversation messages."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    RESULT = "result"
    ERROR = "error"
    
    def __str__(self):
        return self.value


class CodeLanguage(Enum):
    """Supported code languages."""
    PYTHON = "python"
    SHELL = "shell"
    BASH = "bash"
    SH = "sh"
    JAVASCRIPT = "javascript"
    JS = "js"
    
    @classmethod
    def normalize(cls, language: str) -> str:
        """Normalize language string to standard form."""
        lang_lower = language.lower()
        if lang_lower in ["python", "py"]:
            return "python"
        elif lang_lower in ["shell", "bash", "sh", "zsh"]:
            return "shell"
        elif lang_lower in ["javascript", "js", "node"]:
            return "javascript"
        elif lang_lower in ["html", "htm"]:
            return "html"
        elif lang_lower in ["android", "android-shell"]:
            return "android"
        elif lang_lower in ["android-root", "android-su"]:
            return "android-root"
        return lang_lower


@dataclass
class Message:
    """A single message in the conversation."""
    role: MessageRole
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = {
            "role": str(self.role),
            "content": self.content,
            "timestamp": self.timestamp
        }
        if self.metadata:
            data["metadata"] = self.metadata
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create from dictionary."""
        role = MessageRole(data["role"])
        return cls(
            role=role,
            content=data["content"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            metadata=data.get("metadata")
        )


@dataclass
class ExecutionResult:
    """Result of code execution."""
    success: bool
    output: str
    error: str
    return_code: int
    language: str
    execution_time: float = 0.0
    timeout: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @property
    def combined_output(self) -> str:
        """Get combined output and error."""
        parts = []
        if self.output:
            parts.append(self.output)
        if self.error:
            parts.append(f"[Error] {self.error}")
        return "\n".join(parts) if parts else ""


@dataclass
class CodeBlock:
    """A code block extracted from text."""
    language: str
    code: str
    line_number: Optional[int] = None
    
    @property
    def normalized_language(self) -> str:
        """Get normalized language name."""
        return CodeLanguage.normalize(self.language)


@dataclass
class ConversationStats:
    """Statistics about a conversation."""
    total_messages: int = 0
    user_messages: int = 0
    assistant_messages: int = 0
    code_blocks_executed: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time: float = 0.0
    
    def update_from_message(self, message: Message):
        """Update stats from a message."""
        self.total_messages += 1
        if message.role == MessageRole.USER:
            self.user_messages += 1
        elif message.role == MessageRole.ASSISTANT:
            self.assistant_messages += 1
    
    def update_from_execution(self, result: ExecutionResult):
        """Update stats from execution result."""
        self.code_blocks_executed += 1
        if result.success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
        self.total_execution_time += result.execution_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)