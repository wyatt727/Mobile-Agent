#!/usr/bin/env python3
"""
Configuration management for Claude Agent
"""
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path
import json


@dataclass
class AgentConfig:
    """Configuration for Claude Agent."""
    
    # Claude CLI settings
    claude_model: str = "sonnet"
    claude_path: str = "/usr/local/bin/claude"
    claude_system_prompt_file: str = "prompt/Nethunter_Claude.md"  # Path to system prompt file for Claude CLI

    # NetHunter specific settings
    nethunter_mode: bool = False
    adb_path: str = "adb" # Path to ADB executable, assumes in PATH by default
    
    # Execution settings
    execution_timeout: int = 120
    max_fix_attempts: int = 3
    track_dependencies: bool = True
    auto_install_packages: bool = True
    
    # Conversation settings
    max_history_length: int = 100
    conversation_file: str = "conversation.json"
    system_prompt_file: str = "system_prompt.txt"
    context_window_size: int = 10
    
    # File management
    generated_code_dir: str = "generated_code"
    log_file: str = "claude_agent.log"
    
    # Advanced settings
    verbose: bool = False
    save_code_files: bool = True
    use_streaming: bool = False
    retry_on_rate_limit: bool = True
    max_retries: int = 3
    
    @classmethod
    def from_file(cls, config_file: str) -> "AgentConfig":
        """Load configuration from JSON file."""
        if not Path(config_file).exists():
            return cls()
        
        with open(config_file, 'r') as f:
            data = json.load(f)
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        config = cls()
        
        # Override with environment variables if present
        env_mappings = {
            'CLAUDE_MODEL': 'claude_model',
            'CLAUDE_TIMEOUT': 'execution_timeout',
            'CLAUDE_MAX_HISTORY': 'max_history_length',
            'CLAUDE_AUTO_INSTALL': 'auto_install_packages',
            'CLAUDE_VERBOSE': 'verbose',
        }
        
        for env_key, config_key in env_mappings.items():
            if env_value := os.getenv(env_key):
                if config_key in ['execution_timeout', 'max_history_length']:
                    setattr(config, config_key, int(env_value))
                elif config_key in ['auto_install_packages', 'verbose']:
                    setattr(config, config_key, env_value.lower() in ('true', '1', 'yes'))
                else:
                    setattr(config, config_key, env_value)
        
        return config
    
    def save(self, config_file: str):
        """Save configuration to JSON file."""
        with open(config_file, 'w') as f:
            json.dump(self.__dict__, f, indent=2)
    
    def merge(self, overrides: Dict[str, Any]):
        """Merge override values into configuration."""
        for key, value in overrides.items():
            if hasattr(self, key):
                setattr(self, key, value)