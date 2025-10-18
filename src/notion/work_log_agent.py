"""Work log feedback management using Notion API and AI"""

import logging
import os
from datetime import datetime
from typing import Callable, Dict, Optional

import pytz

from .client import NotionClient
from .. import ai

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


def _load_prompt_template(flavor: str = "normal") -> str:
  """
  Load work log feedback prompt template

  Args:
      flavor: Feedback flavor (spicy, normal, mild)

  Returns:
      Prompt template content
  """
  # Map flavor to filename
  flavor_files = {
    "spicy": "work_log_feedback_spicy.txt",
    "normal": "work_log_feedback_normal.txt",
    "mild": "work_log_feedback_mild.txt"
  }

  filename = flavor_files.get(flavor, "work_log_feedback_normal.txt")
  prompt_file = os.path.join(
      os.path.dirname(__file__),
      "..",
      "prompts",
      filename
  )

  try:
    with open(prompt_file, "r", encoding="utf-8") as f:
      return f.read()
  except FileNotFoundError:
    logger.warning(f"⚠️ Prompt file not found: {prompt_file}, using default")
    return "업무일지를 검토하고 피드백을 제공해주세요."


def _load_notion_markdown_guide() -> str:
  """
  Load Notion markdown guide system prompt

  Returns:
      Notion markdown guide content
  """
  guide_file = os.path.join(
      os.path.dirname(__file__),
      "..",
      "prompts",
      "notion_markdown_guide.txt"
  )

  try:
    with open(guide_file, "r", encoding="utf-8") as f:
      return f.read()
  except FileNotFoundError:
    logger.warning(f"⚠️ Notion markdown guide not found: {guide_file}")
    return ""


class WorkLogManager:
  """Manager for work log AI feedback"""

  def __init__(
      self,
      client: Optional[NotionClient] = None,
      ai_provider_type: str = "gemini"
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

    # Load prompt template
    self.prompt_template = _load_prompt_template()
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
    try:
      # Get page blocks (content)
      blocks_response = await self.client.client.blocks.children.list(
          block_id=page_id
      )
      blocks = blocks_response.get("results", [])

      # Extract text from blocks
      content_parts = []
      for block in blocks:
        block_type = block.get("type")
        block_content = block.get(block_type, {})

        # Extract text based on block type
        if "rich_text" in block_content:
          for text_obj in block_content["rich_text"]:
            if "text" in text_obj:
              content_parts.append(text_obj["text"]["content"])

      content = "\n".join(content_parts)
      logger.info(f"📖 Extracted content: {len(content)} characters")
      return content

    except Exception as e:
      logger.error(f"❌ Failed to get page content: {e}")
      raise

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
      system_prompt = _load_notion_markdown_guide()

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
      # Helper: simple fixed-size chunking (<= 1900 chars) for safety margin
      def _chunk_text(text: str, max_len: int = 1900):
        if not text:
          return []
        return [text[i:i + max_len] for i in range(0, len(text), max_len)]

      # Build blocks: divider + header + chunked paragraphs
      header_blocks = [
        {
          "object": "block",
          "type": "divider",
          "divider": {}
        },
        {
          "object": "block",
          "type": "heading_2",
          "heading_2": {
            "rich_text": [
              {
                "type": "text",
                "text": {"content": "🤖 AI 피드백"}
              }
            ]
          }
        },
      ]

      chunk_blocks = [
        {
          "object": "block",
          "type": "paragraph",
          "paragraph": {
            "rich_text": [
              {
                "type": "text",
                "text": {"content": chunk}
              }
            ]
          }
        }
        for chunk in _chunk_text(feedback, 1900)
      ]

      all_blocks = header_blocks + chunk_blocks

      # Notion API: max 100 children per append call -> batch appends
      BATCH_SIZE = 100
      for i in range(0, len(all_blocks), BATCH_SIZE):
        batch = all_blocks[i:i + BATCH_SIZE]
        await self.client.client.blocks.children.append(
            block_id=page_id,
            children=batch
        )

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
        f"🔄 Starting feedback process for date: {date}, flavor: {flavor}, "
        f"database: {database_id}")

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
    self.prompt_template = _load_prompt_template(flavor)

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
    }


# Singleton instance
_work_log_manager = None


def get_work_log_manager(ai_provider_type: str = "gemini") -> WorkLogManager:
  """
  Get or create singleton WorkLogManager instance

  Args:
      ai_provider_type: AI provider type (gemini, claude, ollama)

  Returns:
      WorkLogManager instance
  """
  global _work_log_manager
  if _work_log_manager is None:
    _work_log_manager = WorkLogManager(ai_provider_type=ai_provider_type)
  return _work_log_manager
