"""성과를 STAR 형식으로 변환"""

import logging
from typing import Dict, Optional

from .. import ai
from ..common.prompt_utils import load_prompt
from ..common.singleton import SimpleSingleton

logger = logging.getLogger(__name__)


class AchievementExtractor:
  """성과를 STAR 형식으로 변환하는 추출기"""

  def __init__(self, ai_provider_type: str = "claude"):
    """
    Initialize AchievementExtractor

    Args:
        ai_provider_type: AI provider type (gemini, claude, ollama)
    """
    self.ai_provider_type = ai_provider_type
    self.ai_provider = ai.get_ai_provider(ai_provider_type)
    self.last_used_ai_provider: Optional[str] = None

    # Load prompt template
    self.prompt_template = load_prompt("star_format_converter")
    logger.info(f"✅ AchievementExtractor initialized (AI: {ai_provider_type})")

  async def convert_to_star(
      self,
      achievement_text: str,
      context: Optional[Dict] = None
  ) -> str:
    """
    일반 업무 기록을 STAR 형식으로 변환

    Args:
        achievement_text: 변환할 업무 기록 텍스트
        context: 추가 컨텍스트 (날짜, 프로젝트명 등)

    Returns:
        STAR 형식으로 변환된 텍스트
    """
    try:
      # 컨텍스트 정보 구성
      context_text = ""
      if context:
        context_parts = []
        if context.get("date"):
          context_parts.append(f"날짜: {context['date']}")
        if context.get("project"):
          context_parts.append(f"프로젝트: {context['project']}")
        if context.get("tech_stack"):
          context_parts.append(
              f"사용 기술: {', '.join(context['tech_stack'])}")

        if context_parts:
          context_text = "\n\n## 추가 컨텍스트\n" + "\n".join(context_parts)

      # 프롬프트 생성
      prompt = self.prompt_template.replace(
          "{achievement_text}", achievement_text)
      prompt = prompt.replace("{context}", context_text)

      logger.info(f"🤖 STAR 형식 변환 시작...")

      # AI 변환 실행
      star_text, used_provider = await ai.generate_with_gemini_fallback(
          self.ai_provider_type,
          prompt=prompt,
          system_prompt="당신은 업무 성과를 STAR 형식으로 변환하는 전문가입니다."
      )

      self.last_used_ai_provider = used_provider
      logger.info(f"✅ STAR 형식 변환 완료 (제공자: {used_provider})")

      return star_text.strip()

    except Exception as e:
      logger.error(f"❌ STAR 형식 변환 실패: {e}")
      raise


# Singleton instance
_singleton = SimpleSingleton(AchievementExtractor, param_name="ai_provider_type")


def get_achievement_extractor(ai_provider_type: str = "claude") -> AchievementExtractor:
  """
  Get or create singleton AchievementExtractor instance

  Args:
      ai_provider_type: AI provider type (gemini, claude, ollama)

  Returns:
      AchievementExtractor instance
  """
  return _singleton.get(ai_provider_type=ai_provider_type)
