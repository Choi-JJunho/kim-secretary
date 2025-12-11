"""Gemini AI 제공자 - CLI 방식"""

import asyncio
import logging
import os
import subprocess
from typing import Optional

from .base import AIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
  """Google Gemini CLI 제공자"""

  def __init__(self):
    """Gemini 제공자 초기화"""
    self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
    self.validate_config()
    logger.info(f"✅ Gemini CLI 제공자 초기화: {self.model_name}")

  def validate_config(self) -> bool:
    """Gemini CLI 설치 여부 검증"""
    try:
      result = subprocess.run(
          ["gemini", "--version"],
          capture_output=True,
          text=True,
          timeout=10
      )
      if result.returncode != 0:
        raise ValueError("gemini CLI가 설치되어 있지 않습니다")
      logger.info(f"✅ Gemini CLI 버전: {result.stdout.strip()}")
      return True
    except FileNotFoundError:
      raise ValueError("gemini CLI가 설치되어 있지 않습니다. 'npm install -g @anthropic/gemini-cli' 를 실행하세요")
    except subprocess.TimeoutExpired:
      raise ValueError("gemini CLI 버전 확인 시간 초과")

  async def generate(
      self,
      prompt: str,
      system_prompt: Optional[str] = None,
      **kwargs
  ) -> str:
    """Gemini CLI를 사용하여 응답 생성"""
    try:
      # Combine system prompt with user prompt if provided
      full_prompt = prompt
      if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"

      logger.info("🤖 Gemini CLI 응답 생성 중...")
      
      # Build command
      cmd = ["gemini", full_prompt, "-o", "text"]
      
      # Add model if specified
      if self.model_name:
        cmd.extend(["-m", self.model_name])

      # Run gemini CLI in subprocess (async)
      loop = asyncio.get_event_loop()
      result = await loop.run_in_executor(
          None,
          lambda: subprocess.run(
              cmd,
              capture_output=True,
              text=True,
              timeout=120  # 2분 타임아웃
          )
      )

      if result.returncode != 0:
        error_msg = result.stderr.strip() or "알 수 없는 오류"
        raise RuntimeError(f"Gemini CLI 실행 실패: {error_msg}")

      output = result.stdout.strip()
      logger.info(f"✅ Gemini CLI 응답 생성 완료 ({len(output)}자)")
      return output

    except subprocess.TimeoutExpired:
      logger.error("❌ Gemini CLI 응답 생성 시간 초과 (120초)")
      raise RuntimeError("Gemini CLI 응답 생성 시간 초과")
    except Exception as e:
      logger.error(f"❌ Gemini CLI 응답 생성 실패: {e}")
      raise
