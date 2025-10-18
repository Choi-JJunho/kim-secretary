"""Ollama AI provider"""

import logging
import os
from typing import Optional

import httpx

from .base import AIProvider

logger = logging.getLogger(__name__)


class OllamaProvider(AIProvider):
  """Ollama local AI provider"""

  def __init__(self):
    """Initialize Ollama provider"""
    self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    self.model_name = os.getenv("OLLAMA_MODEL", "llama3.2")
    self.validate_config()
    logger.info(f"✅ Ollama provider initialized: {self.model_name}")

  def validate_config(self) -> bool:
    """Validate Ollama configuration"""
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
    """
    Generate response using Ollama

    Args:
        prompt: User prompt/content
        system_prompt: System instructions
        **kwargs: Additional Ollama parameters

    Returns:
        Generated text
    """
    try:
      logger.info("🤖 Generating Ollama response...")

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
        logger.info(f"✅ Ollama response generated ({len(result)} chars)")
        return result

    except httpx.ConnectError:
      logger.error(
          f"❌ Cannot connect to Ollama at {self.base_url}. "
          "Make sure Ollama is running."
      )
      raise
    except Exception as e:
      logger.error(f"❌ Ollama generation failed: {e}")
      raise
