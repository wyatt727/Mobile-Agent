#!/usr/bin/env python3
"""
Conversation Manager - Handles message history with automatic pruning
"""
import json
import logging
from collections import deque
from pathlib import Path
from typing import List, Dict, Optional, Any, Deque
from datetime import datetime

from claude_agent.utils.models import Message, MessageRole, ConversationStats


logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation history with automatic pruning and persistence."""
    
    def __init__(
        self,
        max_messages: int = 100,
        persist_file: Optional[str] = None,  # Default to None for stateless
        auto_save: bool = False,  # Default to False for stateless
        keep_system_prompt: bool = True
    ):
        """
        Initialize conversation manager.
        
        Args:
            max_messages: Maximum number of messages to keep in memory
            persist_file: File to persist conversation history (None = no persistence)
            auto_save: Whether to automatically save after each message
            keep_system_prompt: Whether to always keep the system prompt
        """
        self.max_messages = max_messages
        self.persist_file = Path(persist_file) if persist_file else None
        self.auto_save = auto_save
        self.keep_system_prompt = keep_system_prompt
        
        # Use deque for efficient message management
        self.messages: Deque[Message] = deque(maxlen=max_messages)
        self.system_prompt: Optional[Message] = None
        self.stats = ConversationStats()
        
        # REMOVED: No loading history for stateless agent
        # Each command should be independent
    
    def add_message(
        self,
        role: str | MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add a message to the conversation.
        
        Args:
            role: Role of the message sender
            content: Content of the message
            metadata: Optional metadata
            
        Returns:
            The created message
        """
        # Convert string role to MessageRole if needed
        if isinstance(role, str):
            role = MessageRole(role)
        
        # Create message
        message = Message(
            role=role,
            content=content,
            metadata=metadata
        )
        
        # Handle system prompt specially
        if role == MessageRole.SYSTEM and self.keep_system_prompt:
            self.system_prompt = message
            logger.debug("System prompt updated")
        else:
            self.messages.append(message)
            self.stats.update_from_message(message)
            logger.debug(f"Added {role} message (total: {len(self.messages)})")
        
        # Auto-save if enabled
        if self.auto_save:
            self.save_history()
        
        return message
    
    def get_context(
        self,
        last_n: int = 10,
        include_system: bool = True,
        roles: Optional[List[MessageRole]] = None
    ) -> List[Dict[str, str]]:
        """
        Get recent context for Claude.
        
        Args:
            last_n: Number of recent messages to include
            include_system: Whether to include system prompt
            roles: Filter for specific roles (None = all roles)
            
        Returns:
            List of messages formatted for Claude
        """
        context = []
        
        # Add system prompt if requested
        if include_system and self.system_prompt:
            context.append({
                "role": str(self.system_prompt.role),
                "content": self.system_prompt.content
            })
        
        # Filter messages by role if specified
        if roles:
            filtered = [msg for msg in self.messages if msg.role in roles]
        else:
            filtered = list(self.messages)
        
        # Get last N messages
        recent = filtered[-last_n:] if last_n else filtered
        
        # Format for Claude
        for msg in recent:
            # Skip result messages in Claude context
            if msg.role != MessageRole.RESULT:
                context.append({
                    "role": str(msg.role),
                    "content": msg.content
                })
        
        logger.debug(f"Built context with {len(context)} messages")
        return context
    
    def get_full_history(self, include_metadata: bool = False) -> List[Dict[str, Any]]:
        """
        Get the full conversation history.
        
        Args:
            include_metadata: Whether to include metadata
            
        Returns:
            Full conversation history
        """
        history = []
        
        # Add system prompt if present
        if self.system_prompt:
            history.append(self.system_prompt.to_dict())
        
        # Add all messages
        for msg in self.messages:
            msg_dict = msg.to_dict()
            if not include_metadata and "metadata" in msg_dict:
                del msg_dict["metadata"]
            history.append(msg_dict)
        
        return history
    
    def save_history(self, file_path: Optional[str] = None):
        """
        Save conversation history to file.
        DISABLED FOR STATELESS AGENT - This method does nothing.
        
        Args:
            file_path: Optional custom file path
        """
        # DISABLED: No saving for stateless agent
        logger.debug("save_history called but disabled for stateless agent")
        return
    
    def load_history(self, file_path: Optional[str] = None):
        """
        Load conversation history from file.
        DISABLED FOR STATELESS AGENT - This method does nothing.
        
        Args:
            file_path: Optional custom file path
        """
        # DISABLED: No loading for stateless agent
        logger.debug("load_history called but disabled for stateless agent")
        return
    
    def clear_history(self, keep_system: bool = True):
        """
        Clear conversation history.
        
        Args:
            keep_system: Whether to keep the system prompt
        """
        self.messages.clear()
        if not keep_system:
            self.system_prompt = None
        
        # Reset stats
        self.stats = ConversationStats()
        
        # Save if auto-save is enabled
        if self.auto_save:
            self.save_history()
        
        logger.info("Cleared conversation history")
    
    def export_markdown(self, file_path: str):
        """
        Export conversation as markdown file.
        
        Args:
            file_path: Path to save markdown file
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Conversation History\n\n")
            
            # Add metadata
            f.write(f"**Date**: {datetime.now().isoformat()}\n")
            f.write(f"**Total Messages**: {len(self.messages)}\n\n")
            f.write("---\n\n")
            
            # Add system prompt
            if self.system_prompt:
                f.write("## System Prompt\n\n")
                f.write(f"{self.system_prompt.content}\n\n")
                f.write("---\n\n")
            
            # Add messages
            for msg in self.messages:
                role_display = msg.role.value.capitalize()
                f.write(f"### {role_display}\n\n")
                f.write(f"{msg.content}\n\n")
                
                if msg.metadata:
                    f.write(f"*Metadata: {json.dumps(msg.metadata, indent=2)}*\n\n")
                
                f.write("---\n\n")
        
        logger.info(f"Exported conversation to {file_path}")
    
    def get_summary(self) -> str:
        """Get a summary of the conversation."""
        return (
            f"Conversation Summary:\n"
            f"  Total messages: {len(self.messages)}\n"
            f"  User messages: {self.stats.user_messages}\n"
            f"  Assistant messages: {self.stats.assistant_messages}\n"
            f"  Code blocks executed: {self.stats.code_blocks_executed}\n"
            f"  Successful executions: {self.stats.successful_executions}\n"
            f"  Failed executions: {self.stats.failed_executions}\n"
            f"  Total execution time: {self.stats.total_execution_time:.2f}s"
        )
    
    def __len__(self) -> int:
        """Get number of messages."""
        return len(self.messages)
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ConversationManager(messages={len(self.messages)}, "
            f"max={self.max_messages}, file='{self.persist_file}')"
        )