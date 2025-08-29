#!/usr/bin/env python3
"""
Claude Agent - Main orchestrator for Claude Code interactions and code execution
"""
import re
import logging
import tempfile
import time
from pathlib import Path
from typing import List, Tuple, Optional
from enum import Enum
from datetime import datetime

from claude_agent.config import AgentConfig
from claude_agent.providers.claude_provider import LLMProvider, ClaudeCodeProvider, FallbackProvider
from claude_agent.core.conversation_manager import ConversationManager
from claude_agent.core.language_executor import LanguageExecutor
from claude_agent.utils.models import (
    MessageRole, ExecutionResult, CodeBlock, ConversationStats
)


logger = logging.getLogger(__name__)


class AgentMode(Enum):
    """Operating modes for the agent."""
    INTERACTIVE = "interactive"
    BATCH = "batch"
    SCRIPT = "script"
    API = "api"


class ClaudeAgent:
    """Main agent orchestrating Claude Code interactions and code execution."""
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm_provider: Optional[LLMProvider] = None,
        language_executor: Optional[LanguageExecutor] = None,
        conversation_manager: Optional[ConversationManager] = None
    ):
        """
        Initialize Claude Agent.
        
        Args:
            config: Agent configuration
            llm_provider: LLM provider (Claude CLI or fallback)
            code_executor: Code executor
            conversation_manager: Conversation manager
        """
        # Use provided config or create default
        self.config = config or AgentConfig()
        
        # Initialize components
        self.llm = llm_provider or self._create_llm_provider()
        self.executor = language_executor or LanguageExecutor(
            timeout=self.config.execution_timeout
        )
        # IMPORTANT: No persistence for stateless agent!
        # Each command should be independent with no memory
        self.conversation = conversation_manager or ConversationManager(
            max_messages=0,  # Don't keep any history
            persist_file=None,  # No persistence file
            auto_save=False  # Never save to disk
        )
        
        # Compile regex patterns (includes hyphenated languages like android-root)
        self.code_block_pattern = re.compile(
            r"```(?P<lang>[\w-]+)?\s*\n(?P<code>.*?)```",
            re.DOTALL | re.IGNORECASE
        )
        
        # Load system prompt if configured (only for non-Claude providers)
        # Claude CLI uses --append-system-prompt flag instead
        if not isinstance(self.llm, ClaudeCodeProvider):
            self._load_system_prompt()
        
        logger.info("Claude Agent initialized")
    
    def _create_error_history_file(self) -> str:
        """
        Create a temporary error history file for tracking retry attempts.
        
        Returns:
            Path to the error history file
        """
        error_file = tempfile.NamedTemporaryFile(mode='w+', suffix='_errors.txt', delete=False)
        error_file.close()
        return error_file.name
    
    def _log_execution_attempt(
        self, 
        error_file_path: str,
        attempt: int,
        original_request: str,
        code: str,
        language: str,
        result: ExecutionResult,
        fix_prompt: Optional[str] = None,
        fix_response: Optional[str] = None
    ):
        """
        Log detailed execution attempt information to error history file.
        
        Args:
            error_file_path: Path to error history file
            attempt: Attempt number (0-based)
            original_request: Original user request
            code: Code that was executed
            language: Programming language
            result: Execution result
            fix_prompt: Fix prompt sent to Claude (if any)
            fix_response: Claude's fix response (if any)
        """
        try:
            with open(error_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"EXECUTION ATTEMPT {attempt + 1}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Language: {language}\n")
                f.write(f"Success: {result.success}\n")
                f.write(f"Return Code: {result.return_code}\n")
                f.write(f"Execution Time: {result.execution_time}s\n")
                f.write(f"{'='*80}\n")
                
                if attempt == 0:
                    f.write(f"ORIGINAL REQUEST:\n{original_request}\n\n")
                
                f.write(f"CODE EXECUTED:\n```{language}\n{code}\n```\n\n")
                
                if result.output:
                    f.write(f"STDOUT OUTPUT:\n{result.output}\n\n")
                
                if result.error:
                    f.write(f"STDERR OUTPUT:\n{result.error}\n\n")
                
                if fix_prompt:
                    f.write(f"FIX PROMPT SENT:\n{fix_prompt}\n\n")
                
                if fix_response:
                    f.write(f"CLAUDE'S FIX RESPONSE:\n{fix_response}\n\n")
                
                f.write(f"\n")
                
        except Exception as e:
            logger.warning(f"Failed to log execution attempt: {e}")
    
    def _create_llm_provider(self) -> LLMProvider:
        """Create the appropriate LLM provider based on configuration."""
        try:
            # Try Claude CLI first
            provider = ClaudeCodeProvider(
                model=self.config.claude_model,
                retry_on_rate_limit=self.config.retry_on_rate_limit,
                max_retries=self.config.max_retries,
                claude_path=self.config.claude_path,
                system_prompt_file=self.config.claude_system_prompt_file
            )
            logger.info("Using Claude Code CLI provider")
            return provider
            
        except RuntimeError as e:
            logger.warning(f"Claude CLI not available: {e}")
            
            # Try fallback provider
            fallback = FallbackProvider()
            if fallback.verify_availability():
                logger.info("Using fallback LLM provider (Ollama)")
                return fallback
            
            raise RuntimeError("No LLM provider available. Please install Claude CLI or Ollama.")
    
    def _load_system_prompt(self):
        """Load system prompt from file if configured."""
        from pathlib import Path
        
        prompt_file = Path(self.config.system_prompt_file)
        if prompt_file.exists():
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    system_prompt = f.read().strip()
                
                if system_prompt:
                    self.conversation.add_message(
                        MessageRole.SYSTEM,
                        system_prompt,
                        metadata={"source": "file"}
                    )
                    logger.info(f"Loaded system prompt from {prompt_file}")
                    
            except Exception as e:
                logger.warning(f"Failed to load system prompt: {e}")
    
    def process_request(
        self,
        user_input: str,
        execute_code: bool = True,
        return_raw: bool = False
    ) -> Tuple[str, List[ExecutionResult]]:
        """
        Process a user request through Claude and execute any code.
        
        Args:
            user_input: User's input/request
            execute_code: Whether to execute extracted code blocks
            return_raw: Return raw response without processing
            
        Returns:
            Tuple of (Claude's response, execution results)
        """
        # Add user message to history
        self.conversation.add_message(MessageRole.USER, user_input)
        
        # Build context for Claude (skip for Claude CLI as it uses system prompt file)
        if isinstance(self.llm, ClaudeCodeProvider):
            context = None  # Claude CLI handles context via --append-system-prompt
        else:
            context = self._build_context()
        
        # Get Claude's response
        try:
            response = self.llm.get_response(user_input, context)
        except Exception as e:
            error_msg = f"Error getting Claude response: {e}"
            logger.error(error_msg)
            self.conversation.add_message(
                MessageRole.ERROR,
                error_msg,
                metadata={"exception": str(type(e).__name__)}
            )
            return error_msg, []
        
        # Add Claude's response to history
        self.conversation.add_message(MessageRole.ASSISTANT, response)
        
        # Return raw if requested
        if return_raw or not execute_code:
            return response, []
        
        # Extract and execute code blocks
        code_blocks = self.extract_code_blocks(response)
        execution_results = []
        
        for i, code_block in enumerate(code_blocks, 1):
            logger.info(f"Processing code block {i}/{len(code_blocks)} ({code_block.language})")
            
            # Execute with retry on failure
            result = self.execute_with_retry(
                code_block.code,
                code_block.language,
                max_attempts=self.config.max_fix_attempts,
                original_request=user_input
            )
            
            execution_results.append(result)
            
            # Add execution result to conversation
            self.conversation.add_message(
                MessageRole.RESULT,
                result.combined_output or "No output",
                metadata={
                    "language": code_block.language,
                    "success": result.success,
                    "execution_time": result.execution_time,
                    "return_code": result.return_code
                }
            )
            
            # Update stats
            self.conversation.stats.update_from_execution(result)
        
        return response, execution_results
    
    def execute_with_retry(
        self,
        code: str,
        language: str,
        max_attempts: int = 3,
        original_request: str = ""
    ) -> ExecutionResult:
        """
        Execute code with automatic fixing attempts on failure.
        Enhanced with error history logging and progressive timeouts.
        
        Args:
            code: Code to execute
            language: Programming language
            max_attempts: Maximum number of fix attempts
            original_request: Original user request for context
            
        Returns:
            Final execution result
        """
        current_code = code
        last_result = None
        error_file_path = None
        
        # Create error history file for retry attempts
        if max_attempts > 1:
            error_file_path = self._create_error_history_file()
            logger.info(f"Created error history file: {error_file_path}")
        
        try:
            for attempt in range(max_attempts):
                # Calculate progressive timeout: base + (90s * attempt)
                # Attempt 0: 120s, Attempt 1: 210s, Attempt 2: 300s (5min)
                timeout = self.config.execution_timeout + (90 * attempt)
                if timeout > 300:  # Cap at 5 minutes
                    timeout = 300
                
                logger.info(f"Attempt {attempt + 1}/{max_attempts} with timeout {timeout}s")
                
                # Temporarily update executor timeout for this attempt
                original_timeout = self.executor.timeout
                self.executor.timeout = timeout
                
                try:
                    # Execute code
                    start_time = time.time()
                    success, stdout, stderr = self.executor.execute(current_code, language)
                    execution_time = time.time() - start_time
                    
                    result = ExecutionResult(
                        success=success,
                        output=stdout,
                        error=stderr,
                        return_code=0 if success else 1,
                        language=language,
                        execution_time=execution_time
                    )
                    last_result = result
                    
                    # Log execution attempt to error history file
                    if error_file_path:
                        self._log_execution_attempt(
                            error_file_path, attempt, original_request, 
                            current_code, language, result
                        )
                    
                    # Return if successful
                    if result.success:
                        if attempt > 0:
                            logger.info(f"Code executed successfully after {attempt + 1} attempts")
                        # Clean up error file if successful
                        if error_file_path:
                            try:
                                Path(error_file_path).unlink(missing_ok=True)
                            except:
                                pass
                        return result
                    
                    # Don't retry if we've reached max attempts
                    if attempt >= max_attempts - 1:
                        logger.warning(f"Code execution failed after {max_attempts} attempts")
                        break
                    
                    # Ask Claude to fix the code
                    logger.info(f"Attempting to fix code (attempt {attempt + 1}/{max_attempts})")
                    fix_prompt = self._build_fix_prompt(current_code, result, language, error_file_path)
                    
                    try:
                        # Get fixed code from Claude
                        fixed_response = self.llm.get_response(fix_prompt)
                        
                        # Log fix interaction to error history
                        if error_file_path:
                            self._log_execution_attempt(
                                error_file_path, attempt, original_request,
                                current_code, language, result, fix_prompt, fixed_response
                            )
                        
                        # Add fix interaction to conversation
                        self.conversation.add_message(
                            MessageRole.USER,
                            fix_prompt,
                            metadata={"type": "fix_request", "attempt": attempt + 1}
                        )
                        self.conversation.add_message(
                            MessageRole.ASSISTANT,
                            fixed_response,
                            metadata={"type": "fix_response", "attempt": attempt + 1}
                        )
                        
                        # Extract fixed code
                        fixed_blocks = self.extract_code_blocks(fixed_response)
                        if fixed_blocks:
                            # Use the first code block of the same language
                            for block in fixed_blocks:
                                if block.normalized_language == language:
                                    current_code = block.code
                                    break
                            else:
                                # No matching language block found
                                logger.warning("No fixed code block found in Claude's response")
                                break
                        else:
                            logger.warning("No code blocks found in fix response")
                            break
                            
                    except Exception as e:
                        logger.error(f"Error getting fix from Claude: {e}")
                        break
                        
                finally:
                    # Restore original timeout
                    self.executor.timeout = original_timeout
            
            return last_result or ExecutionResult(
                success=False,
                output="",
                error="No execution attempted",
                return_code=-1,
                language=language
            )
        
        finally:
            # Clean up error file only if we succeeded, otherwise leave it for debugging
            if error_file_path and last_result and last_result.success:
                try:
                    Path(error_file_path).unlink(missing_ok=True)
                except:
                    pass
            elif error_file_path:
                logger.info(f"Error history preserved at: {error_file_path}")
    
    def extract_code_blocks(self, text: str) -> List[CodeBlock]:
        """
        Extract code blocks from Claude's response.
        
        Args:
            text: Text containing code blocks
            
        Returns:
            List of CodeBlock objects
        """
        blocks = []
        
        for match in self.code_block_pattern.finditer(text):
            language = match.group('lang') or 'text'
            code = match.group('code').strip()
            
            if code:  # Only add non-empty code blocks
                blocks.append(CodeBlock(
                    language=language,
                    code=code,
                    line_number=text[:match.start()].count('\n') + 1
                ))
        
        logger.debug(f"Extracted {len(blocks)} code blocks")
        return blocks
    
    def _build_context(self) -> str:
        """Build context from recent conversation."""
        messages = self.conversation.get_context(
            last_n=self.config.context_window_size,
            include_system=True,
            roles=[MessageRole.USER, MessageRole.ASSISTANT]
        )
        
        # Format as conversation
        context_lines = []
        for msg in messages:
            role = msg['role'].capitalize()
            content = msg['content']
            
            # Truncate very long messages
            if len(content) > 1000:
                content = content[:1000] + "..."
            
            context_lines.append(f"{role}: {content}")
        
        return "\n\n".join(context_lines)
    
    def _build_fix_prompt(
        self,
        code: str,
        result: ExecutionResult,
        language: str,
        error_file_path: Optional[str] = None,
        original_request: str = ""
    ) -> str:
        """Build prompt to fix failed code with full context."""
        error_output = result.error or result.output or "Unknown error"
        
        # Determine if this is a web development request
        is_web_request = any(keyword in original_request.lower() for keyword in [
            'website', 'web', 'html', 'react', 'vue', 'frontend', 'page', 'site',
            'browser', 'deploy', 'server', 'css', 'javascript'
        ])
        
        # Start with system context references
        prompt = """IMPORTANT CONTEXT: You are operating within a NetHunter chroot environment.

Please read and follow these system prompts for proper execution:
@claude_agent/prompt/nethunter-system-prompt-v3.md"""
        
        if is_web_request:
            prompt += """
@claude_agent/prompt/WebDev_Claude.md"""
        
        # Add the original user request to maintain focus on the goal
        prompt += f"""

=== ORIGINAL USER REQUEST ===
{original_request}

=== WHAT WAS ATTEMPTED ===
The following {language} code was generated and executed:

    {code.replace(chr(10), chr(10) + '    ')}

=== COMPLETE ERROR OUTPUT ===
The execution failed with the following output:

STDOUT:
{result.output if result.output else '(no stdout output)'}

STDERR:
{error_output}

Return code: {result.return_code}
Execution time: {result.execution_time}s"""

        # Add error history reference if available
        if error_file_path:
            prompt += f"""

=== ERROR HISTORY AVAILABLE ===
IMPORTANT: For complete context of all previous attempts, please read: @{error_file_path}

This file contains:
- All previous execution attempts with full output
- Previous fix attempts and Claude's responses
- Detailed execution timing for each attempt
- Progressive context showing what has been tried"""

        prompt += f"""

=== YOUR TASK ===
Please analyze the error and provide a solution. You may either:
1. Fix the existing code if the approach is sound
2. Try a completely different approach to achieve the user's goal

Remember to follow the NetHunter system prompt rules.
Return your solution as executable {language} code block(s), following the language identifier rules from the system prompt."""
        
        return prompt
    
    def clear_conversation(self, keep_system: bool = True):
        """
        Clear the conversation history.
        
        Args:
            keep_system: Whether to keep the system prompt
        """
        self.conversation.clear_history(keep_system=keep_system)
        logger.info("Conversation cleared")
    
    def get_stats(self) -> ConversationStats:
        """Get conversation statistics."""
        return self.conversation.stats
    
    def save_conversation(self, file_path: Optional[str] = None):
        """
        Save conversation to file.
        
        Args:
            file_path: Optional custom file path
        """
        self.conversation.save_history(file_path)
    
    def load_conversation(self, file_path: Optional[str] = None):
        """
        Load conversation from file.
        
        Args:
            file_path: Optional custom file path
        """
        self.conversation.load_history(file_path)
    
    def export_conversation_markdown(self, file_path: str):
        """
        Export conversation as markdown.
        
        Args:
            file_path: Path to save markdown file
        """
        self.conversation.export_markdown(file_path)
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ClaudeAgent(provider={type(self.llm).__name__}, "
            f"messages={len(self.conversation)})"
        )