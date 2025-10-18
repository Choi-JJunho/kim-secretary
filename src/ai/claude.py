"""Claude Code CLI provider"""

import asyncio
import logging
import shutil
from typing import Optional

from .base import AIProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(AIProvider):
  """Claude Code CLI provider"""

  def __init__(self):
    """Initialize Claude CLI provider"""
    self.validate_config()
    logger.info("✅ Claude CLI provider initialized")

  def validate_config(self) -> bool:
    """Validate Claude CLI is available"""
    if not shutil.which("claude"):
      raise ValueError(
          "Claude CLI not found. "
          "Install from: https://docs.anthropic.com/claude/docs/claude-cli"
      )
    return True

  async def generate(
      self,
      prompt: str,
      system_prompt: Optional[str] = None,
      **kwargs
  ) -> str:
    """
    Generate response using Claude CLI

    Args:
        prompt: User prompt/content
        system_prompt: System instructions (prepended to prompt)
        **kwargs: Ignored for CLI provider

    Returns:
        Generated text
    """
    try:
      # Combine system prompt with user prompt if provided
      full_prompt = prompt
      if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"

      logger.info("🤖 Generating Claude response via CLI...")

      # Run claude CLI command
      process = await asyncio.create_subprocess_exec(
          "claude",
          "-p",
          full_prompt,
          stdout=asyncio.subprocess.PIPE,
          stderr=asyncio.subprocess.PIPE,
      )

      stdout, stderr = await process.communicate()

      if process.returncode != 0:
        error_msg = stderr.decode() if stderr else "Unknown error"
        raise RuntimeError(f"Claude CLI failed: {error_msg}")

      result = stdout.decode().strip()
      logger.info(f"✅ Claude response generated ({len(result)} chars)")
      return result

    except Exception as e:
      logger.error(f"❌ Claude generation failed: {e}")
      raise
