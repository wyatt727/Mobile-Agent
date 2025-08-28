#!/usr/bin/env python3
"""
Prompt Loader - Manages system prompt selection and context loading
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class PromptLoader:
    """
    Manages loading of system prompts and context files based on environment
    """
    
    def __init__(self, agent_dir: Path = None):
        if agent_dir is None:
            agent_dir = Path(__file__).parent.parent.parent
        
        self.agent_dir = agent_dir
        self.prompt_dir = agent_dir / 'claude_agent' / 'prompt'
        
        # Check environment
        self.is_nethunter = self._detect_nethunter()
        self.is_macos = os.uname().sysname == 'Darwin'
        
        # Priority order for system prompts
        self.system_prompts = {
            'nethunter': [
                'nethunter-system-prompt-v3.md',
                'nethunter-system-prompt-v2.md',
                'nethunter-system-prompt.md'
            ],
            'macos': [
                'system-prompt.txt',
                'CLAUDE.md'
            ],
            'default': [
                'nethunter-system-prompt-v3.md',  # Default to NetHunter v3
                'CLAUDE.md'
            ]
        }
        
        # Context file locations (in priority order)
        self.context_paths = [
            Path('/root'),                    # NetHunter chroot home
            Path.home(),                      # User home
            Path.cwd(),                       # Current directory
            self.prompt_dir,                  # Agent prompt directory
        ]
        
        # Task-specific instruction files
        self.instruction_files = {
            'webdev': 'WebDev_Claude.md',
            'security': 'Security_Claude.md',
            'general': 'CLAUDE.md',
            'nethunter': 'Nethunter_Claude.md'
        }
        
        logger.info(f"PromptLoader initialized. Environment: {'NetHunter' if self.is_nethunter else 'MacOS' if self.is_macos else 'Unknown'}")
    
    def _detect_nethunter(self) -> bool:
        """Detect if running in NetHunter environment"""
        indicators = [
            '/etc/nethunter',
            '/data/local/nhsystem',
            '/root/.nethunter'
        ]
        
        # Check environment variable
        if os.getenv('CLAUDE_NETHUNTER_MODE') == '1':
            return True
        
        # Check for NetHunter indicators
        for indicator in indicators:
            if Path(indicator).exists():
                return True
        
        return False
    
    def get_system_prompt(self) -> str:
        """
        Get the appropriate system prompt based on environment
        
        Returns:
            System prompt content
        """
        # Determine which prompts to try
        if self.is_nethunter:
            prompt_list = self.system_prompts['nethunter']
        elif self.is_macos:
            prompt_list = self.system_prompts['macos']
        else:
            prompt_list = self.system_prompts['default']
        
        # Try each prompt in order
        for prompt_file in prompt_list:
            prompt_path = self.prompt_dir / prompt_file
            if prompt_path.exists():
                logger.info(f"Loading system prompt: {prompt_path}")
                with open(prompt_path, 'r') as f:
                    return f.read()
        
        # Fallback: basic prompt
        logger.warning("No system prompt file found, using basic prompt")
        return self._get_basic_prompt()
    
    def load_context_file(self, filename: str) -> Optional[str]:
        """
        Load a context file from known locations
        
        Args:
            filename: Name of the context file (e.g., 'WebDev_Claude.md')
            
        Returns:
            File content or None if not found
        """
        for path in self.context_paths:
            file_path = path / filename
            if file_path.exists():
                logger.info(f"Loading context file: {file_path}")
                with open(file_path, 'r') as f:
                    return f.read()
        
        logger.debug(f"Context file not found: {filename}")
        return None
    
    def get_task_instructions(self, task_type: str) -> Dict[str, str]:
        """
        Get task-specific instructions
        
        Args:
            task_type: Type of task (webdev, security, etc.)
            
        Returns:
            Dictionary of instruction file names to contents
        """
        instructions = {}
        
        # Get primary instruction file for task
        if task_type in self.instruction_files:
            filename = self.instruction_files[task_type]
            content = self.load_context_file(filename)
            if content:
                instructions[filename] = content
        
        # Always try to load general instructions
        general_content = self.load_context_file('CLAUDE.md')
        if general_content:
            instructions['CLAUDE.md'] = general_content
        
        # In NetHunter, always load NetHunter instructions
        if self.is_nethunter:
            nethunter_content = self.load_context_file('Nethunter_Claude.md')
            if nethunter_content:
                instructions['Nethunter_Claude.md'] = nethunter_content
        
        return instructions
    
    def build_complete_prompt(self, user_request: str = None) -> str:
        """
        Build complete prompt with system prompt and relevant context
        
        Args:
            user_request: Optional user request to detect task type
            
        Returns:
            Complete prompt string
        """
        parts = []
        
        # 1. System prompt
        system_prompt = self.get_system_prompt()
        parts.append(system_prompt)
        
        # 2. Task detection and instructions
        if user_request:
            task_type = self._detect_task_type(user_request)
            instructions = self.get_task_instructions(task_type)
            
            if instructions:
                parts.append("\n## Additional Instructions\n")
                for filename, content in instructions.items():
                    parts.append(f"\n### From {filename}:\n{content}\n")
        
        # 3. Environment context
        env_context = self._get_environment_context()
        if env_context:
            parts.append(f"\n## Current Environment\n{env_context}\n")
        
        return "\n".join(parts)
    
    def _detect_task_type(self, request: str) -> str:
        """Detect task type from user request"""
        request_lower = request.lower()
        
        # Web development patterns
        if any(word in request_lower for word in ['website', 'web', 'html', 'css', 'react', 'blog', 'portfolio', 'landing']):
            return 'webdev'
        
        # Security patterns
        if any(word in request_lower for word in ['scan', 'security', 'vulnerability', 'exploit', 'pentest', 'nmap']):
            return 'security'
        
        # NetHunter-specific patterns
        if any(word in request_lower for word in ['app', 'launch', 'android', 'adb', 'install']):
            return 'nethunter'
        
        return 'general'
    
    def _get_environment_context(self) -> str:
        """Get current environment context"""
        context = []
        
        if self.is_nethunter:
            context.append("- Running in NetHunter chroot environment")
            context.append("- Android device access via ADB")
            
            # Check ADB status
            import subprocess
            try:
                result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=2)
                if 'device' in result.stdout:
                    context.append("- ADB device connected")
            except:
                pass
        
        elif self.is_macos:
            context.append("- Running on MacOS")
            context.append("- Direct filesystem access available")
        
        return "\n".join(context) if context else ""
    
    def _get_basic_prompt(self) -> str:
        """Get basic fallback prompt"""
        if self.is_nethunter:
            return """
You are Claude operating in a NetHunter environment. Execute code in appropriate language blocks:
- bash/shell: Runs in chroot
- android: Runs via adb shell
- android-root: Runs via adb shell su -c
- python: Runs in Python3
- html: Auto-deploys web server

Respond only with executable code blocks.
"""
        else:
            return """
You are Claude, an AI assistant. Execute code in appropriate language blocks:
- bash/shell: Shell commands
- python: Python code
- javascript: JavaScript code

Respond only with executable code blocks.
"""

# Global instance
_loader = None

def get_prompt_loader() -> PromptLoader:
    """Get or create global prompt loader"""
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader