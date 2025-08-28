#!/usr/bin/env python3
"""
Claude Agent - Main orchestrator for Claude Code interactions and code execution
"""
import re
import logging
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum

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
        
        # Compile regex patterns
        self.code_block_pattern = re.compile(
            r"```(?P<lang>\w+)?\s*\n(?P<code>.*?)```",
            re.DOTALL | re.IGNORECASE
        )
        
        # Load system prompt if configured (only for non-Claude providers)
        # Claude CLI uses --append-system-prompt flag instead
        if not isinstance(self.llm, ClaudeCodeProvider):
            self._load_system_prompt()
        
        logger.info("Claude Agent initialized")
    
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
                max_attempts=self.config.max_fix_attempts
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
        max_attempts: int = 3
    ) -> ExecutionResult:
        """
        Execute code with automatic fixing attempts on failure.
        
        Args:
            code: Code to execute
            language: Programming language
            max_attempts: Maximum number of fix attempts
            
        Returns:
            Final execution result
        """
        current_code = code
        last_result = None
        
        for attempt in range(max_attempts):
            # Execute code
            # Execute code and create ExecutionResult
            success, stdout, stderr = self.executor.execute(current_code, language)
            result = ExecutionResult(
                success=success,
                output=stdout,
                error=stderr,
                language=language,
                execution_time=0.0  # LanguageExecutor doesn't track time
            )
            last_result = result
            
            # Return if successful
            if result.success:
                if attempt > 0:
                    logger.info(f"Code executed successfully after {attempt + 1} attempts")
                return result
            
            # Don't retry if we've reached max attempts
            if attempt >= max_attempts - 1:
                logger.warning(f"Code execution failed after {max_attempts} attempts")
                break
            
            # Ask Claude to fix the code
            logger.info(f"Attempting to fix code (attempt {attempt + 1}/{max_attempts})")
            fix_prompt = self._build_fix_prompt(current_code, result, language)
            
            try:
                # Get fixed code from Claude
                fixed_response = self.llm.get_response(fix_prompt)
                
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
        
        return last_result or ExecutionResult(
            success=False,
            output="",
            error="No execution attempted",
            return_code=-1,
            language=language
        )
    
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
        language: str
    ) -> str:
        """Build prompt to fix failed code."""
        error_output = result.error or result.output or "Unknown error"
        
        return f"""The following {language} code failed to execute correctly:

```{language}
{code}
```

Error output:
```
{error_output}
```

Return code: {result.return_code}

Please analyze the error and provide a fixed version of the code. Return ONLY the corrected code in a single {language} code block, without any explanation."""
    
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