"""주간 업무일지 분석기"""

import logging
import os
from typing import Dict, List, Optional

import pytz

from .. import ai

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


def _load_weekly_analysis_prompt() -> str:
  """주간 분석 프롬프트 템플릿 로드"""
  prompt_file = os.path.join(
      os.path.dirname(__file__),
      "..",
      "prompts",
      "weekly_report_analysis.txt"
  )

  try:
    with open(prompt_file, "r", encoding="utf-8") as f:
      return f.read()
  except FileNotFoundError:
    logger.warning(f"⚠️ Prompt file not found: {prompt_file}")
    return ""


class WeeklyAnalyzer:
  """주간 업무일지 분석기"""

  def __init__(self, ai_provider_type: str = "claude"):
    """
    Initialize WeeklyAnalyzer

    Args:
        ai_provider_type: AI provider type (gemini, claude, ollama)
    """
    self.ai_provider_type = ai_provider_type
    self.ai_provider = ai.get_ai_provider(ai_provider_type)
    self.last_used_ai_provider: Optional[str] = None

    # Load prompt template
    self.prompt_template = _load_weekly_analysis_prompt()
    logger.info(f"✅ WeeklyAnalyzer initialized (AI: {ai_provider_type})")

  def extract_work_log_content(self, page: Dict) -> Dict[str, any]:
    """
    Notion 페이지에서 업무일지 내용 추출

    Args:
        page: Notion page object

    Returns:
        업무일지 메타데이터 및 콘텐츠
    """
    properties = page.get("properties", {})

    # 날짜 추출
    date_prop = properties.get("작성일", {}).get("date", {})
    date = date_prop.get("start", "") if date_prop else ""

    # 제목 추출
    title_prop = properties.get("Name", {}) or properties.get("제목", {})
    title_parts = title_prop.get("title", [])
    title = "".join([part.get("plain_text", "") for part in title_parts])

    # 기술스택 추출
    tech_stack_prop = properties.get("기술스택", {}).get("multi_select", [])
    tech_stack = [item.get("name", "") for item in tech_stack_prop]

    # 프로젝트 추출
    project_prop = properties.get("프로젝트", {}).get("select", {})
    project = project_prop.get("name", "") if project_prop else ""

    # 성과타입 추출
    achievement_type_prop = properties.get("성과타입", {}).get("select", {})
    achievement_type = achievement_type_prop.get(
        "name", "") if achievement_type_prop else ""

    # 정량적성과 추출
    quantitative_prop = properties.get("정량적성과", {}).get("rich_text", [])
    quantitative = "".join([part.get("plain_text", "")
                           for part in quantitative_prop])

    return {
      "date": date,
      "title": title,
      "tech_stack": tech_stack,
      "project": project,
      "achievement_type": achievement_type,
      "quantitative": quantitative,
      "page_id": page.get("id", "")
    }

  async def get_page_content(self, page_id: str, notion_client) -> str:
    """
    페이지 본문 내용 가져오기

    Args:
        page_id: Notion page ID
        notion_client: NotionClient instance

    Returns:
        페이지 본문 텍스트
    """
    try:
      blocks_response = await notion_client.client.blocks.children.list(
          block_id=page_id
      )
      blocks = blocks_response.get("results", [])

      content_parts = []
      for block in blocks:
        block_type = block.get("type")
        block_content = block.get(block_type, {})

        if "rich_text" in block_content:
          for text_obj in block_content["rich_text"]:
            if "text" in text_obj:
              content_parts.append(text_obj["text"]["content"])

      return "\n".join(content_parts)
    except Exception as e:
      logger.error(f"❌ Failed to get page content: {e}")
      return ""

  async def analyze_weekly_logs(
      self,
      daily_logs: List[Dict],
      notion_client,
      resume_page_id: Optional[str] = None
  ) -> str:
    """
    주간 업무일지 분석

    Args:
        daily_logs: 일일 업무일지 페이지 목록
        notion_client: NotionClient instance
        resume_page_id: 이력서 페이지 ID (선택)

    Returns:
        마크다운 형식의 분석 결과
    """
    try:
      logger.info(f"📊 주간 분석 시작: {len(daily_logs)}개 업무일지")

      # 업무일지 내용 추출
      work_logs_data = []
      for page in daily_logs:
        metadata = self.extract_work_log_content(page)
        content = await self.get_page_content(metadata["page_id"], notion_client)

        work_log_text = f"""
## {metadata['date']} - {metadata['title']}
**프로젝트**: {metadata['project']}
**성과타입**: {metadata['achievement_type']}
**기술스택**: {', '.join(metadata['tech_stack'])}
**정량적성과**: {metadata['quantitative']}

{content}
"""
        work_logs_data.append(work_log_text.strip())

      # 전체 업무일지 텍스트 결합
      combined_logs = "\n\n---\n\n".join(work_logs_data)

      # 이력서 내용 읽기 (있는 경우)
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

      # 프롬프트 생성
      prompt = self.prompt_template.replace("{work_logs}", combined_logs)
      prompt = prompt.replace("{resume_content}", resume_content if resume_content else "(이력서 정보 없음)")

      logger.info(f"🤖 AI 분석 시작... (내용 길이: {len(combined_logs)}자)")

      # AI 분석 실행
      analysis_text, used_provider = await ai.generate_with_gemini_fallback(
          self.ai_provider_type,
          prompt=prompt,
          system_prompt="당신은 소프트웨어 엔지니어의 업무 기록을 분석하는 전문가입니다. 반드시 마크다운 형식으로만 응답하세요."
      )

      self.last_used_ai_provider = used_provider
      logger.info(f"✅ AI 분석 완료 (제공자: {used_provider})")
      logger.info(f"📋 분석 결과 추출 완료")

      return analysis_text

    except Exception as e:
      logger.error(f"❌ 주간 분석 실패: {e}")
      raise


# Singleton instance
_weekly_analyzer = None


def get_weekly_analyzer(ai_provider_type: str = "claude") -> WeeklyAnalyzer:
  """
  Get or create singleton WeeklyAnalyzer instance

  Args:
      ai_provider_type: AI provider type (gemini, claude, ollama)

  Returns:
      WeeklyAnalyzer instance
  """
  global _weekly_analyzer
  if _weekly_analyzer is None or _weekly_analyzer.ai_provider_type != ai_provider_type:
    _weekly_analyzer = WeeklyAnalyzer(ai_provider_type=ai_provider_type)
  return _weekly_analyzer
