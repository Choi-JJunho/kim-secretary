"""AI provider abstraction layer"""

import logging
from typing import Optional

from .base import AIProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider

logger = logging.getLogger(__name__)

__all__ = [
  "AIProvider",
  "ClaudeProvider",
  "GeminiProvider",
  "OllamaProvider",
  "get_ai_provider",
  "generate_with_gemini_fallback",
]


def get_ai_provider(provider_type: str = "gemini") -> AIProvider:
  """
  Get AI provider instance based on type

  Args:
      provider_type: Type of AI provider (gemini, claude, codex, ollama)

  Returns:
      AIProvider instance
  """
  providers = {
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
    "ollama": OllamaProvider,
  }

  provider_class = providers.get(provider_type.lower())
  if not provider_class:
    raise ValueError(
        f"Unknown provider type: {provider_type}. "
        f"Available: {', '.join(providers.keys())}"
    )

  return provider_class()


async def generate_with_gemini_fallback(
    provider_type: str,
    *,
    prompt: str,
    system_prompt: Optional[str] = None,
    **kwargs,
) -> tuple[str, str]:
  """
  Try generating with the selected provider; on failure, retry once with Gemini.

  Args:
      provider_type: Primary provider type (gemini, claude, ollama)
      prompt: User/content prompt
      system_prompt: Optional system instructions
      **kwargs: Additional provider-specific params

  Returns:
      Tuple of (generated_text, used_provider)
  """
  primary_type = (provider_type or "gemini").lower()

  # If primary is already Gemini, just use it directly
  if primary_type == "gemini":
    provider = get_ai_provider("gemini")
    text = await provider.generate(prompt=prompt, system_prompt=system_prompt, **kwargs)
    return text, "gemini"

  # Try primary provider first
  try:
    provider = get_ai_provider(primary_type)
    text = await provider.generate(prompt=prompt, system_prompt=system_prompt, **kwargs)
    return text, primary_type
  except Exception as e:
    logger.warning(
        f"Primary provider '{primary_type}' failed, retrying with Gemini... Error: {e}")

  # Fallback to Gemini once
  gemini_provider = get_ai_provider("gemini")
  text = await gemini_provider.generate(
      prompt=prompt,
      system_prompt=system_prompt,
      **kwargs,
  )
  return text, "gemini"
