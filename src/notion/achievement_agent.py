"""업무일지 기반 성과 분석 및 STAR 변환 에이전트"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable

import pytz

from .client import NotionClient
from .. import ai
from ..common.prompt_utils import load_prompt
from ..common.notion_utils import extract_page_content
from ..common.singleton import SimpleSingleton
from ..analyzers.achievement_extractor import get_achievement_extractor

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


class AchievementAgent:
  """업무일지에서 성과를 추출하고 STAR 형식으로 변환하는 에이전트"""

  def __init__(
      self,
      client: Optional[NotionClient] = None,
      ai_provider_type: str = "claude"
  ):
    """
    Initialize AchievementAgent

    Args:
        client: NotionClient instance (creates new if None)
        ai_provider_type: AI provider type (gemini, claude, ollama)
    """
    self.client = client or NotionClient()
    self.ai_provider_type = ai_provider_type
    self.ai_provider = ai.get_ai_provider(ai_provider_type)
    self.last_used_ai_provider: Optional[str] = None

    # Load prompts
    self.extraction_prompt_template = load_prompt("achievement_extraction")

    # Get achievement extractor (for STAR conversion)
    self.achievement_extractor = get_achievement_extractor(ai_provider_type)

    logger.info(f"✅ AchievementAgent initialized (AI: {ai_provider_type})")

  async def get_work_logs_by_date_range(
      self,
      database_id: str,
      start_date: str,
      end_date: str
  ) -> List[Dict]:
    """
    특정 기간의 업무일지를 조회

    Args:
        database_id: Notion database ID
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)

    Returns:
        업무일지 페이지 목록
    """
    try:
      filter_params = {
        "and": [
          {
            "property": "작성일",
            "date": {
              "on_or_after": start_date
            }
          },
          {
            "property": "작성일",
            "date": {
              "on_or_before": end_date
            }
          }
        ]
      }

      results = await self.client.query_database(
          database_id=database_id,
          filter_params=filter_params,
          sorts=[{"property": "작성일", "direction": "ascending"}]
      )

      logger.info(f"📅 조회된 업무일지: {len(results)}개 ({start_date} ~ {end_date})")
      return results

    except Exception as e:
      logger.error(f"❌ 업무일지 조회 실패: {e}")
      raise

  async def get_work_log_by_page_id(self, page_id: str) -> Dict:
    """
    특정 페이지 ID로 업무일지 조회

    Args:
        page_id: Notion page ID

    Returns:
        업무일지 페이지
    """
    try:
      page = await self.client.get_page(page_id)
      logger.info(f"📄 업무일지 조회 완료: {page_id}")
      return page
    except Exception as e:
      logger.error(f"❌ 업무일지 조회 실패: {e}")
      raise

  async def extract_achievements(
      self,
      work_log_content: str,
      context: Optional[Dict] = None
  ) -> List[Dict]:
    """
    업무일지 내용에서 성과 추출

    Args:
        work_log_content: 업무일지 내용
        context: 추가 컨텍스트 (날짜, 프로젝트 등)

    Returns:
        추출된 성과 목록 (JSON 배열)
    """
    try:
      # 컨텍스트 정보 구성
      context_text = ""
      if context:
        context_parts = []
        if context.get("date"):
          context_parts.append(f"날짜: {context['date']}")
        if context.get("title"):
          context_parts.append(f"제목: {context['title']}")

        if context_parts:
          context_text = "\n\n## 추가 컨텍스트\n" + "\n".join(context_parts)

      # 프롬프트 생성
      prompt = self.extraction_prompt_template.replace(
          "{work_log_content}", work_log_content)
      prompt = prompt.replace("{context}", context_text)

      logger.info(f"🔍 성과 추출 시작... (내용 길이: {len(work_log_content)}자)")

      # AI 성과 추출 실행
      response, used_provider = await ai.generate_with_gemini_fallback(
          self.ai_provider_type,
          prompt=prompt,
          system_prompt="당신은 업무일지에서 이력서에 활용할 수 있는 의미 있는 성과를 추출하는 전문가입니다. JSON 형식으로만 응답하세요."
      )

      self.last_used_ai_provider = used_provider
      logger.info(f"✅ 성과 추출 완료 (제공자: {used_provider})")

      # JSON 파싱
      try:
        # 마크다운 코드 블록 제거 (```json ... ```)
        response_clean = response.strip()
        if response_clean.startswith("```"):
          # 첫 번째 줄과 마지막 줄 제거
          lines = response_clean.split("\n")
          response_clean = "\n".join(lines[1:-1])

        achievements = json.loads(response_clean)

        if not isinstance(achievements, list):
          logger.warning("⚠️ 성과 추출 결과가 배열이 아닙니다. 빈 배열 반환.")
          return []

        # resume_worthy가 true인 성과만 필터링
        filtered = [a for a in achievements if a.get("resume_worthy", False)]
        logger.info(f"📊 추출된 성과: {len(achievements)}개, 이력서용 성과: {len(filtered)}개")

        return filtered

      except json.JSONDecodeError as e:
        logger.error(f"❌ JSON 파싱 실패: {e}")
        logger.debug(f"응답 내용: {response}")
        return []

    except Exception as e:
      logger.error(f"❌ 성과 추출 실패: {e}")
      raise

  async def convert_to_star(
      self,
      achievement: Dict,
      context: Optional[Dict] = None
  ) -> str:
    """
    추출된 성과를 STAR 형식으로 변환

    Args:
        achievement: 추출된 성과 정보
        context: 추가 컨텍스트

    Returns:
        STAR 형식 텍스트
    """
    try:
      # 성과 정보를 텍스트로 변환
      achievement_text = f"""
제목: {achievement.get('title', '')}
설명: {achievement.get('description', '')}
임팩트: {achievement.get('impact', '')}
사용 기술: {', '.join(achievement.get('tech_stack', []))}
카테고리: {achievement.get('category', '')}
우선순위: {achievement.get('priority', 0)}/10
"""

      # 기존 achievement_extractor 활용
      star_text = await self.achievement_extractor.convert_to_star(
          achievement_text=achievement_text,
          context=context
      )

      return star_text

    except Exception as e:
      logger.error(f"❌ STAR 변환 실패: {e}")
      raise

  async def update_work_log_with_achievements(
      self,
      page_id: str,
      achievements_star: List[str]
  ):
    """
    업무일지에 STAR 성과 추가

    Args:
        page_id: Notion page ID
        achievements_star: STAR 형식 성과 목록
    """
    try:
      if not achievements_star:
        logger.info("📭 추가할 성과가 없습니다.")
        return

      # STAR 성과를 마크다운으로 변환
      star_markdown = "\n\n---\n\n## 🎯 추출된 성과 (STAR)\n\n"
      for i, star in enumerate(achievements_star, 1):
        star_markdown += f"\n### 성과 {i}\n\n{star}\n"

      # Notion 블록으로 변환하여 추가
      from ..common.notion_blocks import markdown_to_notion_blocks, append_blocks_batched

      blocks = markdown_to_notion_blocks(star_markdown)
      await append_blocks_batched(self.client.client, page_id, blocks)

      # "AI 생성 완료" 속성 업데이트
      properties = {
        "AI 생성 완료": {
          "select": {"name": "완료"}
        }
      }
      await self.client.update_page(page_id, properties)

      logger.info(f"✅ 업무일지에 {len(achievements_star)}개 성과 추가 완료: {page_id}")

    except Exception as e:
      logger.error(f"❌ 업무일지 업데이트 실패: {e}")
      raise

  async def analyze_work_log(
      self,
      page_id: str,
      progress_callback: Optional[Callable[[str], any]] = None
  ) -> Dict[str, any]:
    """
    단일 업무일지 성과 분석 워크플로우

    Args:
        page_id: Notion page ID
        progress_callback: Optional callback function to report progress

    Returns:
        분석 결과 딕셔너리
    """
    logger.info(f"🔄 성과 분석 시작: {page_id}")

    # 새 작업 시작 시 사용된 제공자 상태 초기화
    self.last_used_ai_provider = None

    # Helper to call progress callback if provided
    async def update_progress(status: str):
      if progress_callback:
        try:
          await progress_callback(status)
        except Exception as e:
          logger.warning(f"⚠️ Progress callback failed: {e}")

    # 1. 업무일지 조회
    await update_progress("📋 업무일지 조회 중...")
    page = await self.get_work_log_by_page_id(page_id)

    # 페이지 속성에서 정보 추출
    properties = page.get("properties", {})
    title_prop = properties.get("title") or properties.get("Title") or properties.get("제목", {})
    title = ""
    if title_prop.get("title"):
      title = "".join([t.get("plain_text", "") for t in title_prop["title"]])

    date_prop = properties.get("작성일", {})
    date = ""
    if date_prop.get("date"):
      date = date_prop["date"].get("start", "")

    # 2. 페이지 내용 읽기
    await update_progress("📖 업무일지 내용 읽는 중...")
    content = await extract_page_content(self.client, page_id, format="text")

    if not content.strip():
      logger.warning("⚠️ 업무일지 내용이 비어있습니다.")
      return {
        "success": False,
        "page_id": page_id,
        "message": "업무일지 내용이 비어있습니다."
      }

    # 3. 성과 추출
    await update_progress(f"🔍 성과 추출 중... (내용 길이: {len(content)}자)")
    context = {
      "date": date,
      "title": title
    }
    achievements = await self.extract_achievements(content, context)

    if not achievements:
      logger.info("📭 추출된 성과가 없습니다.")
      return {
        "success": True,
        "page_id": page_id,
        "achievements_count": 0,
        "message": "이력서용 성과가 추출되지 않았습니다."
      }

    # 4. STAR 변환
    await update_progress(f"⭐ STAR 변환 중... ({len(achievements)}개 성과)")
    achievements_star = []
    for i, achievement in enumerate(achievements, 1):
      await update_progress(f"⭐ STAR 변환 중... ({i}/{len(achievements)})")
      star_text = await self.convert_to_star(achievement, context)
      achievements_star.append(star_text)

    # 5. Notion 업데이트
    await update_progress("📝 Notion 페이지 업데이트 중...")
    await self.update_work_log_with_achievements(page_id, achievements_star)

    await update_progress("🏁 분석 완료!")
    logger.info(f"✅ 성과 분석 완료: {page_id} ({len(achievements_star)}개 성과)")

    return {
      "success": True,
      "page_id": page_id,
      "achievements_count": len(achievements_star),
      "achievements": achievements,
      "achievements_star": achievements_star,
      "used_ai_provider": self.last_used_ai_provider or self.ai_provider_type
    }

  async def analyze_work_logs_batch(
      self,
      database_id: str,
      start_date: str,
      end_date: str,
      progress_callback: Optional[Callable[[str, int, int], any]] = None
  ) -> Dict[str, any]:
    """
    특정 기간의 업무일지 배치 분석

    Args:
        database_id: Notion database ID
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)
        progress_callback: Optional callback function to report progress (message, current, total)

    Returns:
        배치 분석 결과
    """
    logger.info(f"🔄 배치 성과 분석 시작: {start_date} ~ {end_date}")

    # 1. 업무일지 조회
    work_logs = await self.get_work_logs_by_date_range(
        database_id, start_date, end_date
    )

    if not work_logs:
      logger.info("📭 조회된 업무일지가 없습니다.")
      return {
        "success": True,
        "total": 0,
        "analyzed": 0,
        "failed": 0,
        "results": []
      }

    # 2. 각 업무일지 분석
    total = len(work_logs)
    results = []
    analyzed = 0
    failed = 0

    for i, work_log in enumerate(work_logs, 1):
      page_id = work_log["id"]

      # 진행 상황 콜백
      if progress_callback:
        try:
          await progress_callback(f"분석 중... ({i}/{total})", i, total)
        except Exception as e:
          logger.warning(f"⚠️ Progress callback failed: {e}")

      try:
        result = await self.analyze_work_log(page_id)
        results.append(result)

        if result.get("success"):
          analyzed += 1
        else:
          failed += 1

      except Exception as e:
        logger.error(f"❌ 업무일지 분석 실패 ({page_id}): {e}")
        failed += 1
        results.append({
          "success": False,
          "page_id": page_id,
          "error": str(e)
        })

    logger.info(f"✅ 배치 분석 완료: 총 {total}개, 성공 {analyzed}개, 실패 {failed}개")

    return {
      "success": True,
      "total": total,
      "analyzed": analyzed,
      "failed": failed,
      "results": results
    }


# Singleton instance
_singleton = SimpleSingleton(AchievementAgent, param_name="ai_provider_type")


def get_achievement_agent(ai_provider_type: str = "claude") -> AchievementAgent:
  """
  Get or create singleton AchievementAgent instance

  Args:
      ai_provider_type: AI provider type (gemini, claude, ollama)

  Returns:
      AchievementAgent instance
  """
  return _singleton.get(ai_provider_type=ai_provider_type)
