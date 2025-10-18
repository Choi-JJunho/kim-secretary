"""Base AI provider interface"""

from abc import ABC, abstractmethod
from typing import Optional


class AIProvider(ABC):
  """Abstract base class for AI providers"""

  @abstractmethod
  async def generate(
      self,
      prompt: str,
      system_prompt: Optional[str] = None,
      **kwargs
  ) -> str:
    """
    Generate AI response

    Args:
        prompt: User prompt/content to analyze
        system_prompt: System instructions (optional)
        **kwargs: Provider-specific parameters

    Returns:
        Generated text response
    """
    pass

  @abstractmethod
  def validate_config(self) -> bool:
    """
    Validate provider configuration

    Returns:
        True if configuration is valid

    Raises:
        ValueError: If configuration is invalid
    """
    pass
