"""월간 리포트 분석기"""

import logging
from typing import Dict, List, Optional

from ..ai import generate_with_gemini_fallback
from ..common.prompt_utils import load_prompt
from ..common.notion_utils import extract_page_content
from ..common.singleton import SimpleSingleton

logger = logging.getLogger(__name__)


class MonthlyAnalyzer:
  """월간 주간 리포트 종합 분석기"""

  def __init__(self, ai_provider_type: str = "claude"):
    """
    Initialize MonthlyAnalyzer

    Args:
        ai_provider_type: AI provider type (gemini, claude, ollama)
    """
    self.ai_provider_type = ai_provider_type
    self.last_used_ai_provider: Optional[str] = None

    # 프롬프트 로드
    self.prompt_template = load_prompt("monthly_report_analysis")

    logger.info(f"✅ MonthlyAnalyzer initialized (AI: {ai_provider_type})")

  async def analyze_monthly_reports(
      self,
      weekly_reports: List[Dict],
      notion_client,
      resume_page_id: Optional[str] = None
  ) -> str:
    """
    월간 주간 리포트 종합 분석

    Args:
        weekly_reports: 주간 리포트 페이지 목록 (Notion API 응답)
        notion_client: NotionClient 인스턴스
        resume_page_id: 이력서 페이지 ID (선택)

    Returns:
        마크다운 형식의 분석 결과
    """
    logger.info(f"📊 월간 분석 시작: {len(weekly_reports)}개 주간 리포트")

    # 1. 각 주간 리포트에서 메타데이터 및 콘텐츠 추출
    weekly_data = []
    for page in weekly_reports:
      metadata = self.extract_weekly_report_metadata(page)
      content = await self.get_page_content(metadata["page_id"], notion_client)

      # 주차 정보와 콘텐츠 결합
      report_text = f"## {metadata['week']} ({metadata['start_date']} ~ {metadata['end_date']})\n\n{content}"
      weekly_data.append(report_text.strip())

    # 2. 모든 주간 리포트 결합
    combined_reports = "\n\n---\n\n".join(weekly_data)

    # 3. 이력서 내용 읽기 (있는 경우)
    resume_content = ""
    if resume_page_id:
      try:
        logger.info(f"📄 이력서 페이지 읽기: {resume_page_id}")
        resume_content = await self.get_page_content(resume_page_id, notion_client)
        if resume_content:
          logger.info(f"✅ 이력서 내용 로드 완료 ({len(resume_content)}자)")
        else:
          logger.warning("⚠️ 이력서 페이지가 비어있습니다")
      except Exception as e:
        logger.warning(f"⚠️ 이력서 읽기 실패 (선택사항): {e}")
        resume_content = ""

    # 4. AI 분석 요청
    prompt = self.prompt_template.replace("{weekly_reports}", combined_reports)
    prompt = prompt.replace("{resume_content}", resume_content if resume_content else "(이력서 정보 없음)")

    logger.info(f"🤖 AI 분석 시작... (내용 길이: {len(combined_reports)}자)")

    analysis_text, used_provider = await generate_with_gemini_fallback(
        self.ai_provider_type,
        prompt=prompt,
        system_prompt="""당신은 커리어 코치이자 이력서 작성 전문가입니다.

주간 리포트 개수와 관계없이 제공된 데이터를 기반으로 월간 리포트를 생성하세요.

**중요**:
- 마크다운 형식으로 응답하세요
- 프롬프트의 마크다운 구조를 정확히 따르세요
- "데이터가 부족합니다" 같은 응답은 금지입니다
- 주간 리포트가 1개만 있어도 해당 데이터를 기반으로 최선의 월간 분석을 제공하세요"""
    )

    self.last_used_ai_provider = used_provider
    logger.info(f"✅ AI 분석 완료 (제공자: {used_provider})")

    # 4. 마크다운 추출 (코드 블록 제거)
    import re
    # ```markdown ... ``` 블록이 있으면 추출
    markdown_match = re.search(r'```markdown\s*\n(.*?)```', analysis_text, re.DOTALL)
    if markdown_match:
      analysis_text = markdown_match.group(1).strip()
    else:
      # 일반 ``` ... ``` 블록이 있으면 추출
      code_match = re.search(r'```\s*\n(.*?)```', analysis_text, re.DOTALL)
      if code_match:
        analysis_text = code_match.group(1).strip()

    logger.info("📋 분석 결과 추출 완료")
    return analysis_text.strip()

  def extract_weekly_report_metadata(self, page: Dict) -> Dict:
    """
    주간 리포트 페이지에서 메타데이터 추출

    Args:
        page: Notion 페이지 객체

    Returns:
        메타데이터 딕셔너리
    """
    properties = page.get("properties", {})

    # 주차 (Title)
    week_prop = properties.get("주차", {})
    week_title = week_prop.get("title", [])
    week = week_title[0]["text"]["content"] if week_title else "Unknown"

    # 시작일
    start_date_prop = properties.get("시작일", {})
    start_date_obj = start_date_prop.get("date", {})
    start_date = start_date_obj.get("start", "") if start_date_obj else ""

    # 종료일
    end_date_prop = properties.get("종료일", {})
    end_date_obj = end_date_prop.get("date", {})
    end_date = end_date_obj.get("start", "") if end_date_obj else ""

    return {
      "page_id": page["id"],
      "week": week,
      "start_date": start_date,
      "end_date": end_date
    }

  async def get_page_content(self, page_id: str, notion_client) -> str:
    """
    Notion 페이지 콘텐츠 가져오기

    Args:
        page_id: Notion 페이지 ID
        notion_client: NotionClient 인스턴스

    Returns:
        페이지 콘텐츠 (마크다운 형식)
    """
    return await extract_page_content(notion_client, page_id, format="markdown")


# Singleton instance
_singleton = SimpleSingleton(MonthlyAnalyzer, param_name="ai_provider_type")


def get_monthly_analyzer(ai_provider_type: str = "claude") -> MonthlyAnalyzer:
  """
  Get or create singleton MonthlyAnalyzer instance

  Args:
      ai_provider_type: AI provider type (gemini, claude, ollama)

  Returns:
      MonthlyAnalyzer instance
  """
  return _singleton.get(ai_provider_type=ai_provider_type)
