"""Handle work log feedback requests from webhook bot messages"""

import json
import logging
import os
import re
from typing import Dict, Optional

from slack_bolt.async_app import AsyncApp

from ..notion.work_log_agent import get_work_log_manager
from ..common.slack_utils import (
  build_initial_text,
  build_progress_text,
  get_used_ai_label,
)

logger = logging.getLogger(__name__)

# Target channel for webhook messages
WEBHOOK_CHANNEL_ID = os.getenv("SLACK_WORK_LOG_WEBHOOK_CHANNEL_ID")
# Target channel for report messages
REPORT_CHANNEL_ID = os.getenv("SLACK_WORK_LOG_REPORT_CHANNEL_ID")


def parse_work_log_message(message_text: str) -> Optional[Dict]:
  """메시지 텍스트에서 업무일지 피드백 요청 파싱 (JSON 형식)

  지원 형식 (JSON 문자열):
  {
    "action": "work_log_feedback",
    "date": "2025-10-18",
    "database_id": "...",
    "ai_provider": "gemini",
    "flavor": "normal",
    "user_id": "U12345678"
  }

  필수: action, date, database_id
  선택: ai_provider(gemini 기본), flavor(normal 기본), user_id
  """
  try:
    data = json.loads(message_text.strip())
    if data.get("action") == "work_log_feedback":
      return {
        "date": data.get("date"),
        "ai_provider": data.get("ai_provider", "gemini"),
        "flavor": data.get("flavor", "normal"),
        "user_id": data.get("user_id"),
        "database_id": data.get("database_id")  # Optional: uses env var if not provided
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
    database_id = parsed_data.get("database_id")  # Required

    # Validate date format
    if not date or not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
      await client.chat_postMessage(
          channel=REPORT_CHANNEL_ID,
          text=f"❌ 잘못된 날짜 형식입니다: {date}\n올바른 형식: YYYY-MM-DD"
      )
      return

    # Validate database_id is provided
    if not database_id:
      await client.chat_postMessage(
          channel=REPORT_CHANNEL_ID,
          text=f"❌ database_id가 필요합니다.\nJSON에 database_id를 포함해주세요."
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

    # Create manager upfront to allow dynamic AI labeling (may remain selected value until fallback occurs)
    work_log_mgr = get_work_log_manager(ai_provider_type=ai_provider)
    used_ai_label = get_used_ai_label(work_log_mgr, ai_provider)

    # Send initial response with dynamic AI label
    initial_message = await client.chat_postMessage(
        channel=REPORT_CHANNEL_ID,
        text=build_initial_text(
          user_mention=user_mention,
          date=date,
          ai_label=used_ai_label,
          flavor_line=f"🌶️ 맛: {flavor}",
        )
    )

    message_ts = initial_message.get("ts")

    # Process feedback
    try:
      # work_log_mgr already created above

      # Progress update function (reflects fallback provider if it occurs)
      async def update_progress(status: str):
        try:
          used_ai = get_used_ai_label(work_log_mgr, ai_provider)
          await client.chat_update(
              channel=REPORT_CHANNEL_ID,
              ts=message_ts,
              text=build_progress_text(
                user_mention=user_mention,
                date=date,
                ai_label=used_ai,
                flavor_line=f"🌶️ 맛: {flavor}",
                status=status,
              )
          )
        except Exception as e:
          logger.warning(f"⚠️ 진행 상태 업데이트 실패: {e}")
      result = await work_log_mgr.process_feedback(
          date=date,
          database_id=database_id,
          flavor=flavor,
          progress_callback=update_progress
      )

      # Success response
      used_ai = (result.get('used_ai_provider') if isinstance(result, dict) else None) or ai_provider
      await client.chat_update(
          channel=REPORT_CHANNEL_ID,
          ts=message_ts,
          text=(
            f"✅ {user_mention}업무일지 AI 피드백 생성 완료!\n\n"
            f"📅 날짜: {date}\n"
            f"🤖 AI: {used_ai.upper()}\n"
            f"🌶️ 맛: {flavor}\n"
            f"📄 페이지 ID: {result['page_id']}\n"
            f"📝 피드백 길이: {result['feedback_length']}자"
          )
      )

      logger.info(f"✅ Work log feedback completed: {result}")

    except ValueError as ve:
      # Validation error (page not found, already completed, etc.)
      used_ai = (getattr(work_log_mgr, 'last_used_ai_provider', None) or ai_provider).upper()
      await client.chat_update(
          channel=REPORT_CHANNEL_ID,
          ts=message_ts,
          text=(
            f"⚠️ {user_mention}업무일지 피드백 생성 실패\n\n"
            f"📅 날짜: {date}\n"
            f"🤖 AI: {used_ai}\n"
            f"🌶️ 맛: {flavor}\n\n"
            f"❌ 오류: {str(ve)}"
          )
      )
      logger.warning(f"⚠️ Validation error: {ve}")

    except Exception as e:
      # Unexpected error
      used_ai = (getattr(work_log_mgr, 'last_used_ai_provider', None) or ai_provider).upper()
      await client.chat_update(
          channel=REPORT_CHANNEL_ID,
          ts=message_ts,
          text=(
            f"❌ {user_mention}업무일지 피드백 생성 중 오류 발생\n\n"
            f"📅 날짜: {date}\n"
            f"🤖 AI: {used_ai}\n"
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
