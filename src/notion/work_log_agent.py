"""Notion API와 AI를 활용한 업무일지 피드백 관리"""

import logging
from datetime import datetime
from typing import Callable, Dict, Optional

import pytz

from .client import NotionClient
from .. import ai
from ..common.prompt_utils import load_prompt
from ..common.notion_utils import extract_page_content
from ..common.singleton import SimpleSingleton

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


class WorkLogManager:
  """업무일지 AI 피드백 처리 매니저"""

  def __init__(
      self,
      client: Optional[NotionClient] = None,
      ai_provider_type: str = "claude"
  ):
    """
    Initialize WorkLogManager

    Args:
        client: NotionClient instance (creates new if None)
        ai_provider_type: AI provider type (gemini, claude, ollama)
    """
    self.client = client or NotionClient()
    self.ai_provider_type = ai_provider_type
    self.ai_provider = ai.get_ai_provider(ai_provider_type)
    self.last_used_ai_provider: Optional[str] = None

    # Prompt template will be loaded based on flavor in process_feedback
    self.prompt_template = ""
    logger.info(f"✅ WorkLogManager initialized (AI: {ai_provider_type})")

  async def find_work_log_by_date(
      self,
      date: str,
      database_id: str
  ) -> Optional[Dict]:
    """
    Find work log page by date

    Args:
        date: Date string in ISO format (YYYY-MM-DD)
        database_id: Notion database ID (required)

    Returns:
        First matching page or None
    """
    try:
      filter_params = {
        "property": "작성일",
        "date": {
          "equals": date
        }
      }

      results = await self.client.query_database(
          database_id=database_id,
          filter_params=filter_params
      )

      if not results:
        logger.info(f"📭 No work log found for date: {date}")
        return None

      page = results[0]  # Use first result if multiple exist
      logger.info(f"📄 Found work log: {page['id']}")
      return page

    except Exception as e:
      logger.error(f"❌ Failed to find work log: {e}")
      raise

  async def check_feedback_status(self, page_id: str) -> bool:
    """
    Check if feedback is already completed

    Args:
        page_id: Notion page ID

    Returns:
        True if feedback is completed
    """
    try:
      page = await self.client.get_page(page_id)
      properties = page.get("properties", {})

      feedback_status = properties.get("AI 검토 완료 여부", {})
      status_value = feedback_status.get("select") or {}
      status_name = status_value.get("name", "")

      is_completed = status_name == "완료"
      logger.info(
          f"📊 Feedback status: {status_name} (completed: {is_completed})")
      return is_completed

    except Exception as e:
      logger.error(f"❌ Failed to check feedback status: {e}")
      raise

  async def get_page_content(self, page_id: str) -> str:
    """
    Get page content as plain text

    Args:
        page_id: Notion page ID

    Returns:
        Page content as text
    """
    content = await extract_page_content(self.client, page_id, format="text")
    logger.info(f"📖 Extracted content: {len(content)} characters")
    return content

  async def generate_feedback(self, work_log_content: str) -> str:
    """
    Generate AI feedback for work log

    Args:
        work_log_content: Work log content text

    Returns:
        AI-generated feedback
    """
    try:
      current_date = datetime.now(KST).strftime("%Y-%m-%d")

      # Load Notion markdown guide as system prompt
      system_prompt = load_prompt("notion_markdown_guide")

      # Build full prompt
      prompt = f"{self.prompt_template}\n\n## 업무일지 내용\n\n{work_log_content}"
      prompt = prompt.replace("{date}", current_date)

      # Generate feedback using selected AI provider, with Gemini fallback on failure
      feedback, used_provider = await ai.generate_with_gemini_fallback(
          self.ai_provider_type,
          prompt=prompt,
          system_prompt=system_prompt,
      )
      # Track the actual provider used (for logs/UI)
      self.last_used_ai_provider = used_provider
      logger.info(f"✅ AI feedback generated ({len(feedback)} chars)")
      return feedback

    except Exception as e:
      logger.error(f"❌ Failed to generate feedback: {e}")
      raise

  async def append_feedback_to_page(self, page_id: str, feedback: str):
    """
    Append AI feedback to page content

    Args:
        page_id: Notion page ID
        feedback: Feedback text to append
    """
    try:
      # 공통 유틸을 사용해 블록 생성 및 배치 추가
      from ..common.notion_blocks import build_ai_feedback_blocks, append_blocks_batched

      blocks = build_ai_feedback_blocks(feedback)
      await append_blocks_batched(self.client.client, page_id, blocks)

      logger.info(f"✅ Feedback appended to page: {page_id}")

    except Exception as e:
      logger.error(f"❌ Failed to append feedback: {e}")
      raise

  async def mark_feedback_complete(self, page_id: str):
    """
    Mark feedback as completed

    Args:
        page_id: Notion page ID
    """
    try:
      properties = {
        "AI 검토 완료 여부": {
          "select": {"name": "완료"}
        }
      }

      await self.client.update_page(page_id, properties)
      logger.info(f"✅ Marked feedback complete: {page_id}")

    except Exception as e:
      logger.error(f"❌ Failed to mark feedback complete: {e}")
      raise

  async def process_feedback(
      self,
      date: str,
      database_id: str,
      flavor: str = "normal",
      progress_callback: Optional[Callable[[str], any]] = None
  ) -> Dict[str, any]:
    """
    Process feedback workflow for a specific date

    Args:
        date: Date string in ISO format (YYYY-MM-DD)
        database_id: Notion database ID (required)
        flavor: Feedback flavor (spicy, normal, mild)
        progress_callback: Optional callback function to report progress

    Returns:
        Result dictionary with status and message

    Raises:
        ValueError: If page not found or already completed
    """
    logger.info(
        f"🔄 피드백 처리 시작: 날짜={date}, 맛={flavor}, 데이터베이스={database_id}")

    # 새 작업 시작 시 사용된 제공자 상태 초기화 (진행 라벨 일관성 유지)
    self.last_used_ai_provider = None

    # Helper to call progress callback if provided
    async def update_progress(status: str):
      if progress_callback:
        try:
          await progress_callback(status)
        except Exception as e:
          logger.warning(f"⚠️ Progress callback failed: {e}")

    # 1. Find work log page
    await update_progress("📋 업무일지 검색 중...")
    page = await self.find_work_log_by_date(date, database_id=database_id)
    if not page:
      raise ValueError(f"업무일지를 찾을 수 없습니다: {date}")

    page_id = page["id"]

    # 2. Check if already completed
    await update_progress("✅ 업무일지 발견! 피드백 상태 확인 중...")
    is_completed = await self.check_feedback_status(page_id)
    if is_completed:
      raise ValueError(
          f"이미 AI 피드백이 완료된 업무일지입니다. (날짜: {date})"
      )

    # 3. Get page content
    await update_progress("📖 업무일지 내용 읽는 중...")
    content = await self.get_page_content(page_id)
    if not content.strip():
      raise ValueError("업무일지 내용이 비어있습니다.")

    # 4. Load prompt template for selected flavor
    await update_progress("🎨 피드백 프롬프트 준비 중...")
    flavor_files = {
      "spicy": "work_log_feedback_spicy",
      "normal": "work_log_feedback_normal",
      "mild": "work_log_feedback_mild"
    }
    prompt_name = flavor_files.get(flavor, "work_log_feedback_normal")
    self.prompt_template = load_prompt(prompt_name, default="업무일지를 검토하고 피드백을 제공해주세요.")

    # 5. Generate AI feedback
    await update_progress(f"🤖 AI 피드백 생성 중... (내용 길이: {len(content)}자)")
    feedback = await self.generate_feedback(content)
    # If fallback occurred, notify via progress update
    try:
      if self.last_used_ai_provider and \
         self.last_used_ai_provider.lower() != (self.ai_provider_type or "").lower():
        await update_progress(
            f"⚠️ 선택한 AI({self.ai_provider_type}) 실패로 "
            f"{self.last_used_ai_provider.upper()}로 대체하여 생성했습니다.")
        logger.info(
            f"🔁 AI provider fallback: {self.ai_provider_type} -> {self.last_used_ai_provider}")
    except Exception as _:
      # Do not fail the flow due to progress notification issues
      pass

    # 6. Append feedback to page
    await update_progress("📝 Notion 페이지에 피드백 추가 중...")
    await self.append_feedback_to_page(page_id, feedback)

    # 7. Mark as complete
    await update_progress("🏁 마무리 중...")
    await self.mark_feedback_complete(page_id)

    logger.info(f"✅ Feedback process completed for date: {date}")
    return {
      "success": True,
      "date": date,
      "page_id": page_id,
      "feedback_length": len(feedback),
      "used_ai_provider": self.last_used_ai_provider or self.ai_provider_type,
      "feedback": feedback,
    }


# Singleton instance
_singleton = SimpleSingleton(WorkLogManager, param_name="ai_provider_type")


def get_work_log_manager(ai_provider_type: str = "claude") -> WorkLogManager:
  """
  Get or create singleton WorkLogManager instance

  Args:
      ai_provider_type: AI provider type (gemini, claude, ollama)

  Returns:
      WorkLogManager instance
  """
  return _singleton.get(ai_provider_type=ai_provider_type)