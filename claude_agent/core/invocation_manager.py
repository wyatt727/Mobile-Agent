#!/usr/bin/env python3
"""
Invocation Manager - Handles flexible Claude invocation with context loading
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class InvocationManager:
    """Manages how Claude is invoked with proper context and instructions"""
    
    def __init__(self, base_prompt_file: Path = None):
        """
        Initialize invocation manager
        
        Args:
            base_prompt_file: Path to base system prompt (nethunter-system-prompt-precise.md)
        """
        if base_prompt_file is None:
            base_prompt_file = Path(__file__).parent.parent / 'prompt' / 'nethunter-system-prompt-precise.md'
        
        self.base_prompt_file = base_prompt_file
        self.instruction_dirs = [
            Path('/root'),  # NetHunter chroot home
            Path.home(),    # Current user home
            Path.cwd(),     # Current working directory
            Path(__file__).parent.parent / 'prompt'  # Agent prompt directory
        ]
        
        # Priority order for instruction files (higher priority first)
        self.instruction_files = [
            'TASK_SPECIFIC.md',    # Task-specific overrides
            'WebDev_Claude.md',     # Web development instructions
            'Security_Claude.md',   # Security-specific instructions  
            'Nethunter_Claude.md',  # NetHunter-specific instructions
            'CLAUDE.md',            # General instructions
        ]
        
        # Patterns that trigger specific instruction loading
        self.task_patterns = {
            'webdev': ['website', 'web page', 'html', 'css', 'react', 'blog', 'portfolio', 
                      'web', 'game', 'canvas', 'javascript', 'site', 'webpage',
                      'html5', 'deploy', 'server', 'localhost'],
            'security': ['scan', 'nmap', 'exploit', 'vulnerability', 'pentest', 'hack'],
            'android': ['app', 'apk', 'install', 'package', 'activity'],
            'system': ['status', 'info', 'battery', 'storage', 'memory'],
        }
    
    def build_system_prompt(self, user_request: str) -> str:
        """
        Build complete system prompt with context based on request
        
        Args:
            user_request: The user's natural language request
            
        Returns:
            Complete system prompt with all relevant instructions
        """
        prompt_parts = []
        
        # 1. Load base system prompt
        if self.base_prompt_file.exists():
            with open(self.base_prompt_file, 'r') as f:
                base_prompt = f.read()
                prompt_parts.append(base_prompt)
                logger.info(f"Loaded base prompt from {self.base_prompt_file}")
        
        # 2. Detect task type from request
        task_type = self._detect_task_type(user_request)
        logger.info(f"Detected task type: {task_type or 'general'}")
        
        # 3. Load relevant instruction files
        loaded_instructions = self._load_instructions(task_type)
        if loaded_instructions:
            prompt_parts.append("\n## Additional Context and Instructions\n")
            for name, content in loaded_instructions.items():
                prompt_parts.append(f"\n### From {name}:\n{content}\n")
        
        # 4. Add dynamic context
        dynamic_context = self._get_dynamic_context()
        if dynamic_context:
            prompt_parts.append(f"\n## Current Environment\n{dynamic_context}\n")
        
        return "\n".join(prompt_parts)
    
    def format_request(self, user_request: str, system_prompt: str = None) -> Dict:
        """
        Format the complete request for Claude
        
        Args:
            user_request: The user's natural language request
            system_prompt: Optional override for system prompt
            
        Returns:
            Formatted request dictionary ready for Claude API
        """
        if system_prompt is None:
            system_prompt = self.build_system_prompt(user_request)
        
        # Check for explicit instruction loading directive
        if "@" in user_request:
            user_request, additional_context = self._parse_directives(user_request)
            if additional_context:
                system_prompt += f"\n## User-Specified Context\n{additional_context}\n"
        
        # Format as Claude expects
        return {
            'system': system_prompt,
            'messages': [
                {
                    'role': 'user',
                    'content': user_request
                }
            ],
            'metadata': {
                'task_type': self._detect_task_type(user_request),
                'has_instructions': bool(self._load_instructions(None)),
                'environment': 'nethunter'
            }
        }
    
    def _detect_task_type(self, request: str) -> Optional[str]:
        """Detect task type from user request"""
        request_lower = request.lower()
        
        for task_type, patterns in self.task_patterns.items():
            for pattern in patterns:
                if pattern in request_lower:
                    return task_type
        
        return None
    
    def _load_instructions(self, task_type: Optional[str]) -> Dict[str, str]:
        """Load relevant instruction files based on task type"""
        loaded = {}
        
        # Determine which files to prioritize
        priority_files = []
        
        if task_type == 'webdev':
            priority_files = ['WebDev_Claude.md']
        elif task_type == 'security':
            priority_files = ['Security_Claude.md', 'Nethunter_Claude.md']
        elif task_type == 'android':
            priority_files = ['Nethunter_Claude.md']
        
        # Always check for general instructions
        priority_files.extend(['CLAUDE.md', 'Nethunter_Claude.md'])
        
        # Search for instruction files
        for instruction_file in priority_files:
            for dir_path in self.instruction_dirs:
                file_path = dir_path / instruction_file
                if file_path.exists() and file_path.name not in loaded:
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            loaded[instruction_file] = content
                            logger.info(f"Loaded instructions from {file_path}")
                            break  # Use first found instance of each file
                    except Exception as e:
                        logger.warning(f"Failed to load {file_path}: {e}")
        
        return loaded
    
    def _get_dynamic_context(self) -> str:
        """Get dynamic environment context"""
        context_parts = []
        
        # Check if we're in NetHunter
        if os.path.exists('/etc/nethunter'):
            context_parts.append("- Running in NetHunter chroot")
        
        # Check ADB status
        try:
            import subprocess
            clean_env = {
                'PATH': '/usr/bin:/bin:/usr/local/bin:/usr/sbin:/sbin',
                'LC_ALL': 'C',
            }
            result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=2, env=clean_env)
            if 'device' in result.stdout and 'unauthorized' not in result.stdout:
                context_parts.append("- ADB device connected and authorized")
            elif 'unauthorized' in result.stdout:
                context_parts.append("- ADB device connected but UNAUTHORIZED (retry needed)")
            else:
                context_parts.append("- No ADB device connected")
        except:
            context_parts.append("- ADB status unknown")
        
        # Check for available tools
        tools = []
        for tool in ['nmap', 'msfconsole', 'airmon-ng', 'node', 'npm']:
            try:
                result = subprocess.run(['which', tool], capture_output=True, timeout=1, env=clean_env)
                if result.returncode == 0:
                    tools.append(tool)
            except:
                pass
        
        if tools:
            context_parts.append(f"- Available tools: {', '.join(tools)}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def _parse_directives(self, request: str) -> tuple[str, str]:
        """
        Parse @ directives from user request
        
        Example: "follow @Security_Claude.md and scan target.com"
        Returns: ("scan target.com", <contents of Security_Claude.md>)
        """
        import re
        
        # Find @ references
        pattern = r'@(\S+\.md)'
        matches = re.findall(pattern, request)
        
        if not matches:
            return request, ""
        
        additional_context = []
        
        for filename in matches:
            # Remove @ reference from request
            request = request.replace(f'@{filename}', '').strip()
            request = request.replace('follow and', '').replace('follow', '').strip()
            
            # Try to load the file
            for dir_path in self.instruction_dirs:
                file_path = dir_path / filename
                if file_path.exists():
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            additional_context.append(f"### {filename}:\n{content}")
                            logger.info(f"Loaded user-specified file: {file_path}")
                            break
                    except Exception as e:
                        logger.warning(f"Failed to load {file_path}: {e}")
        
        return request, "\n".join(additional_context)

class RequestProcessor:
    """Processes requests with proper invocation"""
    
    def __init__(self, invocation_manager: InvocationManager = None):
        if invocation_manager is None:
            invocation_manager = InvocationManager()
        self.invocation_manager = invocation_manager
    
    def process(self, user_request: str, claude_client) -> tuple[str, list]:
        """
        Process a user request with proper context
        
        Args:
            user_request: Natural language request from user
            claude_client: Claude API client
            
        Returns:
            Tuple of (response_text, execution_results)
        """
        # Build the formatted request
        formatted_request = self.invocation_manager.format_request(user_request)
        
        # Log what we're sending
        logger.info(f"Task type: {formatted_request['metadata']['task_type']}")
        logger.info(f"Has instructions: {formatted_request['metadata']['has_instructions']}")
        
        # Send to Claude
        response = claude_client.send_message(
            system=formatted_request['system'],
            messages=formatted_request['messages']
        )
        
        # Extract and execute code blocks
        execution_results = self._extract_and_execute(response)
        
        return response, execution_results
    
    def _extract_and_execute(self, response: str) -> list:
        """Extract code blocks from response and execute them"""
        import re
        from claude_agent.core.code_executor_enhanced import NetHunterCodeExecutor
        
        executor = NetHunterCodeExecutor(nethunter_mode=True)
        results = []
        
        # Pattern to match code blocks with language
        pattern = r'```(\w+)\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        for language, code in matches:
            logger.info(f"Executing {language} code block")
            
            # Map special language identifiers
            if language == 'adb':
                # Wrap in adb shell using system sh to bypass shell config
                escaped_code = code.replace("'", "'\\\\''")
                code = f"adb shell /system/bin/sh -c '{escaped_code}'"
                language = 'shell'
            elif language == 'host':
                # Wrap in adb shell su using system sh to bypass shell config
                escaped_code = code.replace("'", "'\\\\''")
                code = f"adb shell su -c '/system/bin/sh -c \"{escaped_code}\"'"
                language = 'shell'
            
            # Execute the code
            result = executor.execute_with_context(code, language)
            results.append(result)
        
        return results