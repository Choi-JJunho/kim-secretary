"""Ollama 로컬 AI 제공자"""

import logging
import os
from typing import Optional

import httpx

from .base import AIProvider

logger = logging.getLogger(__name__)


class OllamaProvider(AIProvider):
  """Ollama 로컬 AI 제공자"""

  def __init__(self):
    """Ollama 제공자 초기화"""
    self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    self.model_name = os.getenv("OLLAMA_MODEL", "llama3.2")
    self.validate_config()
    logger.info(f"✅ Ollama provider initialized: {self.model_name}")

  def validate_config(self) -> bool:
    """Ollama 설정 검증"""
    # Just validate URL format, actual connectivity is checked on use
    if not self.base_url.startswith("http"):
      raise ValueError(
          f"Invalid OLLAMA_BASE_URL: {self.base_url}. "
          "Must start with http:// or https://"
      )
    return True

  async def generate(
      self,
      prompt: str,
      system_prompt: Optional[str] = None,
      **kwargs
  ) -> str:
    """Ollama를 사용하여 응답 생성"""
    try:
      logger.info("🤖 Ollama 응답 생성 중...")

      async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {
          "model": self.model_name,
          "prompt": prompt,
          "stream": False,
          **kwargs
        }

        if system_prompt:
          payload["system"] = system_prompt

        response = await client.post(
            f"{self.base_url}/api/generate",
            json=payload
        )
        response.raise_for_status()

        result = response.json()["response"]
        logger.info(f"✅ Ollama 응답 생성 완료 ({len(result)}자)")
        return result

    except httpx.ConnectError:
      logger.error(
          f"❌ {self.base_url} 에서 Ollama에 연결할 수 없습니다. Ollama가 실행 중인지 확인하세요."
      )
      raise
    except Exception as e:
      logger.error(f"❌ Ollama 응답 생성 실패: {e}")
      raise
