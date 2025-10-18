"""Claude Code CLI 제공자 (로컬 CLI)"""

import asyncio
import logging
import os
import shutil
from typing import Optional

from .base import AIProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(AIProvider):
  """Claude Code CLI 제공자"""

  def __init__(self):
    """Claude CLI 제공자 초기화"""
    self.validate_config()
    logger.info("✅ Claude CLI provider initialized")

  def validate_config(self) -> bool:
    """Validate Claude CLI is available and authenticated"""
    if not shutil.which("claude"):
      raise ValueError(
          "Claude CLI not found. "
          "Install from: https://docs.anthropic.com/claude/docs/claude-cli"
      )

    # Check if authentication directory exists
    auth_dir = os.path.expanduser("~/.claude")
    if not os.path.exists(auth_dir):
      logger.warning(
          "⚠️ Claude auth directory not found at ~/.claude. "
          "You may need to run 'claude auth login' first."
      )

    return True

  async def generate(
      self,
      prompt: str,
      system_prompt: Optional[str] = None,
      **kwargs
  ) -> str:
    """Claude CLI를 사용하여 응답 생성"""
    try:
      # Combine system prompt with user prompt if provided
      full_prompt = prompt
      if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"

      logger.info("🤖 Claude CLI 응답 생성 중...")

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
      logger.info(f"✅ Claude 응답 생성 완료 ({len(result)}자)")
      return result

    except Exception as e:
      logger.error(f"❌ Claude 응답 생성 실패: {e}")
      raise
