"""Handle work log feedback requests from webhook bot messages"""

import json
import logging
import os
import re
from typing import Dict, Optional

from slack_bolt.async_app import AsyncApp

from ..notion.work_log_agent import get_work_log_manager

logger = logging.getLogger(__name__)

# Target channel for webhook messages
WEBHOOK_CHANNEL_ID = os.getenv("SLACK_WORK_LOG_WEBHOOK_CHANNEL_ID")
# Target channel for report messages
REPORT_CHANNEL_ID = os.getenv("SLACK_WORK_LOG_REPORT_CHANNEL_ID")


def parse_work_log_message(message_text: str) -> Optional[Dict]:
  """
  Parse work log feedback request from message text

  Supports JSON format only:
  ```json
  {
    "action": "work_log_feedback",
    "date": "2025-10-18",
    "ai_provider": "gemini",
    "flavor": "normal",
    "user_id": "U12345678"
  }
  ```

  Args:
      message_text: Message text to parse

  Returns:
      Parsed data dictionary or None if not a valid request
  """
  try:
    data = json.loads(message_text.strip())
    if data.get("action") == "work_log_feedback":
      return {
        "date": data.get("date"),
        "ai_provider": data.get("ai_provider", "gemini"),
        "flavor": data.get("flavor", "normal"),
        "user_id": data.get("user_id")
      }
  except (json.JSONDecodeError, ValueError):
    pass

  return None


async def handle_work_log_webhook_message(
    message: Dict,
    say,
    client
):
  """
  Handle work log feedback request from webhook bot

  Args:
      message: Message event
      say: Slack say function (unused, kept for compatibility)
      client: Slack client
  """
  try:
    # Check if message is from the webhook channel
    channel_id = message.get("channel")
    if channel_id != WEBHOOK_CHANNEL_ID:
      return

    # Parse message
    message_text = message.get("text", "")
    parsed_data = parse_work_log_message(message_text)

    if not parsed_data:
      return  # Not a work log feedback request

    logger.info(f"📥 Received work log feedback request: {parsed_data}")

    # Extract parameters
    date = parsed_data.get("date")
    ai_provider = parsed_data.get("ai_provider", "gemini")
    flavor = parsed_data.get("flavor", "normal")
    user_id = parsed_data.get("user_id")

    # Validate date format
    if not date or not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
      await client.chat_postMessage(
          channel=REPORT_CHANNEL_ID,
          text=f"❌ 잘못된 날짜 형식입니다: {date}\n올바른 형식: YYYY-MM-DD"
      )
      return

    # Validate AI provider
    valid_providers = ["gemini", "claude", "codex", "ollama"]
    if ai_provider not in valid_providers:
      await client.chat_postMessage(
          channel=REPORT_CHANNEL_ID,
          text=f"❌ 지원하지 않는 AI 제공자입니다: {ai_provider}\n"
               f"사용 가능: {', '.join(valid_providers)}"
      )
      return

    # Validate flavor
    valid_flavors = ["spicy", "normal", "mild"]
    if flavor not in valid_flavors:
      await client.chat_postMessage(
          channel=REPORT_CHANNEL_ID,
          text=f"❌ 잘못된 피드백 맛 옵션입니다: {flavor}\n"
               f"사용 가능: {', '.join(valid_flavors)}"
      )
      return

    # Prepare user mention
    user_mention = f"<@{user_id}>님의 " if user_id else ""

    # Send initial response
    initial_message = await client.chat_postMessage(
        channel=REPORT_CHANNEL_ID,
        text=f"🚀 {user_mention}업무일지 AI 피드백 생성을 시작합니다.\n\n"
             f"📅 날짜: {date}\n"
             f"🤖 AI: {ai_provider.upper()}\n"
             f"🌶️ 맛: {flavor}\n\n"
             f"⏳ 처리 중..."
    )

    message_ts = initial_message.get("ts")

    # Progress update function
    async def update_progress(status: str):
      try:
        await client.chat_update(
            channel=REPORT_CHANNEL_ID,
            ts=message_ts,
            text=(
              f"🚀 {user_mention}업무일지 AI 피드백 생성 중...\n\n"
              f"📅 날짜: {date}\n"
              f"🤖 AI: {ai_provider.upper()}\n"
              f"🌶️ 맛: {flavor}\n\n"
              f"{status}"
            )
        )
      except Exception as e:
        logger.warning(f"⚠️ Failed to update progress: {e}")

    # Process feedback
    try:
      work_log_mgr = get_work_log_manager(ai_provider_type=ai_provider)
      result = await work_log_mgr.process_feedback(
          date=date,
          flavor=flavor,
          progress_callback=update_progress
      )

      # Success response
      await client.chat_update(
          channel=REPORT_CHANNEL_ID,
          ts=message_ts,
          text=(
            f"✅ {user_mention}업무일지 AI 피드백 생성 완료!\n\n"
            f"📅 날짜: {date}\n"
            f"🤖 AI: {ai_provider.upper()}\n"
            f"🌶️ 맛: {flavor}\n"
            f"📄 페이지 ID: {result['page_id']}\n"
            f"📝 피드백 길이: {result['feedback_length']}자"
          )
      )

      logger.info(f"✅ Work log feedback completed: {result}")

    except ValueError as ve:
      # Validation error (page not found, already completed, etc.)
      await client.chat_update(
          channel=REPORT_CHANNEL_ID,
          ts=message_ts,
          text=(
            f"⚠️ {user_mention}업무일지 피드백 생성 실패\n\n"
            f"📅 날짜: {date}\n"
            f"🤖 AI: {ai_provider.upper()}\n"
            f"🌶️ 맛: {flavor}\n\n"
            f"❌ 오류: {str(ve)}"
          )
      )
      logger.warning(f"⚠️ Validation error: {ve}")

    except Exception as e:
      # Unexpected error
      await client.chat_update(
          channel=REPORT_CHANNEL_ID,
          ts=message_ts,
          text=(
            f"❌ {user_mention}업무일지 피드백 생성 중 오류 발생\n\n"
            f"📅 날짜: {date}\n"
            f"🤖 AI: {ai_provider.upper()}\n"
            f"🌶️ 맛: {flavor}\n\n"
            f"오류: {str(e)}"
          )
      )
      logger.error(f"❌ Failed to process work log feedback: {e}", exc_info=True)

  except Exception as e:
    logger.error(f"❌ Error in work log webhook handler: {e}", exc_info=True)


def register_work_log_webhook_handler(app: AsyncApp):
  """
  Register work log webhook message handler

  Note: This is now handled by chat_handlers.py message event handler
  This function is kept for compatibility but does nothing.

  Args:
      app: Slack AsyncApp instance
  """
  logger.info("✅ Work log webhook handler registered (via chat_handlers)")
