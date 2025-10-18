"""Gemini AI 제공자"""

import logging
import os
from typing import Optional

import google.generativeai as genai

from .base import AIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
  """Google Gemini AI 제공자"""

  def __init__(self):
    """Gemini 제공자 초기화"""
    self.api_key = os.getenv("GEMINI_API_KEY")
    self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    self.validate_config()

    genai.configure(api_key=self.api_key)
    self.model = genai.GenerativeModel(self.model_name)
    logger.info(f"✅ Gemini 제공자 초기화: {self.model_name}")

  def validate_config(self) -> bool:
    """Gemini 환경 변수 검증"""
    if not self.api_key:
      raise ValueError("GEMINI_API_KEY 환경 변수가 필요합니다")
    return True

  async def generate(
      self,
      prompt: str,
      system_prompt: Optional[str] = None,
      **kwargs
  ) -> str:
    """Gemini를 사용하여 응답 생성"""
    try:
      # Combine system prompt with user prompt if provided
      full_prompt = prompt
      if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"

      logger.info("🤖 Gemini 응답 생성 중...")
      response = await self.model.generate_content_async(
          full_prompt,
          **kwargs
      )

      result = response.text
      logger.info(f"✅ Gemini 응답 생성 완료 ({len(result)}자)")
      return result

    except Exception as e:
      logger.error(f"❌ Gemini 응답 생성 실패: {e}")
      raise
