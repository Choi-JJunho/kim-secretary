"""AI provider abstraction layer"""

from .base import AIProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider

__all__ = ["AIProvider", "ClaudeProvider", "GeminiProvider", "OllamaProvider"]


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
