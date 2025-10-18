"""Gemini AI provider"""

import logging
import os
from typing import Optional

import google.generativeai as genai

from .base import AIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
  """Google Gemini AI provider"""

  def __init__(self):
    """Initialize Gemini provider"""
    self.api_key = os.getenv("GEMINI_API_KEY")
    self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    self.validate_config()

    genai.configure(api_key=self.api_key)
    self.model = genai.GenerativeModel(self.model_name)
    logger.info(f"✅ Gemini provider initialized: {self.model_name}")

  def validate_config(self) -> bool:
    """Validate Gemini configuration"""
    if not self.api_key:
      raise ValueError("GEMINI_API_KEY environment variable is required")
    return True

  async def generate(
      self,
      prompt: str,
      system_prompt: Optional[str] = None,
      **kwargs
  ) -> str:
    """
    Generate response using Gemini

    Args:
        prompt: User prompt/content
        system_prompt: System instructions (prepended to prompt)
        **kwargs: Additional Gemini parameters

    Returns:
        Generated text
    """
    try:
      # Combine system prompt with user prompt if provided
      full_prompt = prompt
      if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"

      logger.info("🤖 Generating Gemini response...")
      response = await self.model.generate_content_async(
          full_prompt,
          **kwargs
      )

      result = response.text
      logger.info(f"✅ Gemini response generated ({len(result)} chars)")
      return result

    except Exception as e:
      logger.error(f"❌ Gemini generation failed: {e}")
      raise
