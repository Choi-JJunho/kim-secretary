"""AI 제공자 추상화 계층"""

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
  """타입에 따른 AI 제공자 인스턴스 생성"""
  providers = {
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
    "ollama": OllamaProvider,
  }

  provider_class = providers.get(provider_type.lower())
  if not provider_class:
    raise ValueError(
        f"알 수 없는 AI 제공자 타입입니다: {provider_type}. "
        f"사용 가능: {', '.join(providers.keys())}"
    )

  return provider_class()


async def generate_with_gemini_fallback(
    provider_type: str,
    *,
    prompt: str,
    system_prompt: Optional[str] = None,
    **kwargs,
) -> tuple[str, str]:
  """선택한 제공자로 먼저 생성 시도 후, 실패 시 한 번 Gemini로 대체 시도

  Args:
      provider_type: 기본 제공자 타입 (gemini, claude, ollama)
      prompt: 사용자/콘텐츠 프롬프트
      system_prompt: 시스템 지시문 (선택)
      **kwargs: 추가 제공자별 파라미터

  Returns:
      (생성된_텍스트, 실제_사용된_제공자)
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
        f"기본 제공자 '{primary_type}' 사용에 실패하여 Gemini로 대체 시도합니다. 오류: {e}")

  # Fallback to Gemini once
  gemini_provider = get_ai_provider("gemini")
  text = await gemini_provider.generate(
      prompt=prompt,
      system_prompt=system_prompt,
      **kwargs,
  )
  return text, "gemini"
