#!/usr/bin/env python3
"""
Claude Code CLI Provider - Interfaces with Claude via CLI
"""
import subprocess
import json
import os
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def get_response(self, prompt: str, context: Optional[str] = None) -> str:
        """Get response from the LLM."""
        pass
    
    @abstractmethod
    def verify_availability(self) -> bool:
        """Verify the provider is available."""
        pass


class ClaudeCodeProvider(LLMProvider):
    """Provider for Claude Code CLI integration."""
    
    def __init__(
        self,
        model: str = "sonnet",
        timeout: int = 120,
        retry_on_rate_limit: bool = True,
        max_retries: int = 3,
        claude_path: str = "/usr/local/bin/claude",
        system_prompt_file: Optional[str] = None
    ):
        """
        Initialize Claude Code CLI provider.
        
        Args:
            model: Claude model to use (sonnet, opus, etc.)
            timeout: Command timeout in seconds
            retry_on_rate_limit: Whether to retry on rate limits
            max_retries: Maximum number of retry attempts
            claude_path: Path to Claude CLI executable
            system_prompt_file: Path to system prompt file
        """
        self.model = model
        self.timeout = timeout
        self.retry_on_rate_limit = retry_on_rate_limit
        self.max_retries = max_retries
        self.claude_path = claude_path
        self.system_prompt_file = system_prompt_file
        self._cli_available = None
        
        # Convert system prompt file to absolute path if provided
        if self.system_prompt_file:
            from pathlib import Path
            self.system_prompt_file = str(Path(self.system_prompt_file).absolute())
        
        # Verify CLI on initialization
        if not self.verify_availability():
            raise RuntimeError("Claude Code CLI is not available")
    
    def verify_availability(self) -> bool:
        """Verify Claude Code CLI is installed and configured."""
        if self._cli_available is not None:
            return self._cli_available
        
        # Check if the Claude CLI path exists
        from pathlib import Path
        if not Path(self.claude_path).exists():
            logger.warning(f"Claude CLI not found at: {self.claude_path}")
            # Try fallback to 'claude' in PATH
            self.claude_path = "claude"
        
        try:
            result = subprocess.run(
                [self.claude_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            self._cli_available = result.returncode == 0
            
            if self._cli_available:
                logger.info(f"Claude CLI verified: {result.stdout.strip()}")
            else:
                logger.error(f"Claude CLI error: {result.stderr.strip()}")
                
        except FileNotFoundError:
            logger.error("Claude Code CLI not found. Please install it first.")
            self._cli_available = False
        except subprocess.TimeoutExpired:
            logger.error("Claude CLI verification timed out")
            self._cli_available = False
        except Exception as e:
            logger.error(f"Error verifying Claude CLI: {e}")
            self._cli_available = False
        
        return self._cli_available
    
    def get_response(self, prompt: str, context: Optional[str] = None) -> str:
        """
        Get response from Claude using CLI.
        
        Args:
            prompt: The prompt to send to Claude
            context: Optional context to prepend to the prompt
            
        Returns:
            Claude's response as a string
        """
        full_prompt = self._build_prompt(prompt, context)
        
        for attempt in range(self.max_retries):
            try:
                response = self._call_claude_cli(full_prompt)
                return response
                
            except RateLimitError as e:
                if not self.retry_on_rate_limit or attempt == self.max_retries - 1:
                    raise
                    
                wait_time = min(2 ** attempt, 30)  # Exponential backoff, max 30s
                logger.warning(f"Rate limited. Waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}")
                time.sleep(wait_time)
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                logger.warning(f"Error on attempt {attempt + 1}/{self.max_retries}: {e}")
                time.sleep(1)
        
        raise RuntimeError(f"Failed to get response after {self.max_retries} attempts")
    
    def _build_prompt(self, prompt: str, context: Optional[str]) -> str:
        """Build the full prompt with context."""
        if context:
            return f"{context}\n\n---\n\n{prompt}"
        return prompt
    
    def _escape_for_shell(self, text: str) -> str:
        """Escape text for use in single-quoted shell strings.
        
        In bash, to include a single quote in a single-quoted string,
        we need to end the quote, add an escaped single quote, and start a new quote.
        Example: 'don't' becomes 'don'\''t'
        """
        return text.replace("'", "'\\''")
    
    def _call_claude_cli(self, prompt: str) -> str:
        """Call Claude CLI with the prompt."""
        try:
            # If system prompt file is available, prepend the instruction
            if self.system_prompt_file:
                full_prompt = f"strictly follow your role and instructions within @{self.system_prompt_file} and: {prompt}"
            else:
                full_prompt = prompt
            
            # Escape the prompt for shell
            escaped_prompt = self._escape_for_shell(full_prompt)
            
            # Build command as a shell string to ensure proper handling
            cmd_parts = [
                self.claude_path,
                "--print"
            ]
            
            # Add model if specified
            if self.model:
                cmd_parts.extend(["--model", self.model])
            
            # Build the full command with the prompt in single quotes
            cmd_str = " ".join(cmd_parts) + f" '{escaped_prompt}'"
            
            logger.debug(f"Executing Claude CLI (model: {self.model})")
            
            # Execute command using shell=True to properly handle the quoted prompt
            result = subprocess.run(
                cmd_str,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode == 0:
                response = result.stdout.strip()
                logger.debug(f"Got response of length {len(response)}")
                return response
            else:
                error_msg = result.stderr.strip()
                
                # Check for rate limiting
                if "rate limit" in error_msg.lower():
                    raise RateLimitError(error_msg)
                
                # Check for authentication errors
                if "unauthorized" in error_msg.lower() or "api key" in error_msg.lower():
                    raise AuthenticationError(error_msg)
                
                raise ClaudeAPIError(f"Claude CLI error: {error_msg}")
                
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Claude CLI timed out after {self.timeout} seconds")


class FallbackProvider(LLMProvider):
    """Fallback provider using Ollama or other local LLMs."""
    
    def __init__(
        self,
        api_url: str = "http://127.0.0.1:11434/api/chat",
        model: str = "deepseek-coder-v2",
        timeout: int = 120
    ):
        """Initialize fallback provider."""
        self.api_url = api_url
        self.model = model
        self.timeout = timeout
        self.session = None
    
    def verify_availability(self) -> bool:
        """Verify the fallback provider is available."""
        try:
            import requests
            if self.session is None:
                self.session = requests.Session()
            
            response = self.session.get(
                self.api_url.replace("/api/chat", "/api/tags"),
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def get_response(self, prompt: str, context: Optional[str] = None) -> str:
        """Get response from fallback LLM."""
        import requests
        
        if self.session is None:
            self.session = requests.Session()
        
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": full_prompt}],
            "stream": False
        }
        
        try:
            response = self.session.post(
                self.api_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("message", {}).get("content", "")
            
        except requests.exceptions.RequestException as e:
            raise ClaudeAPIError(f"Fallback LLM error: {e}")


# Custom exceptions
class ClaudeAPIError(Exception):
    """Base exception for Claude API errors."""
    pass


class RateLimitError(ClaudeAPIError):
    """Rate limit error from Claude API."""
    pass


class AuthenticationError(ClaudeAPIError):
    """Authentication error from Claude API."""
    pass


class TimeoutError(ClaudeAPIError):
    """Timeout error from Claude API."""
    pass