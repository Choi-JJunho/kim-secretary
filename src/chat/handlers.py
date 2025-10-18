"""Chat message event handlers"""

import json
import logging
import os
import re
from datetime import datetime

import pytz

from ..commands.work_log_webhook_handler import handle_work_log_webhook_message
from ..notion.wake_up import get_wake_up_manager
from ..notion.work_log_agent import get_work_log_manager
from ..common.slack_utils import (
  build_initial_text,
  build_progress_text,
  flavor_emoji,
  flavor_label,
  get_used_ai_label,
)

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')

# Webhook channel ID
WEBHOOK_CHANNEL_ID = os.getenv("SLACK_WORK_LOG_WEBHOOK_CHANNEL_ID")
# Report channel ID
REPORT_CHANNEL_ID = os.getenv("SLACK_WORK_LOG_REPORT_CHANNEL_ID")


def register_chat_handlers(app):
  """Register all chat-related event handlers"""

  # Work log webhook handler - JSON format only
  @app.message(re.compile(r'\{"action"\s*:\s*"work_log_feedback"'))
  async def handle_work_log_webhook(message, say, client):
    """Handle work log feedback webhook message from incoming webhook"""
    # Check if message is from webhook channel
    channel_id = message.get("channel")
    if channel_id != WEBHOOK_CHANNEL_ID:
      return

    logger.info(f"📥 Received work log webhook request")
    await handle_work_log_webhook_message(message, say, client)

  @app.action("wake_up_complete")
  async def handle_wake_up_complete(ack, body, client, logger):
    """Handle wake-up complete button click"""
    await ack()

    user_id = body["user"]["id"]
    user_name = body["user"].get("name", user_id)
    wake_up_time = datetime.now(KST)

    try:
      wake_up_mgr = get_wake_up_manager()
      await wake_up_mgr.record_wake_up(
          user_id=user_id,
          user_name=user_name,
          wake_up_time=wake_up_time
      )

      logger.info(f"✅ Wake-up recorded for {user_name} ({user_id})")

      # Get total wake-up count for this user
      total_count = await wake_up_mgr.get_wake_up_count(user_id)

      # Format time as HH:MM
      time_str = wake_up_time.strftime("%H:%M")

      # Create completion message
      completion_text = (
        f"기상 완료! \"{time_str}\"시에 기상하셨네요 🙏\n"
        f"지금까지 총 {total_count}번 기상확인을 했습니다."
      )

      # Update the message to remove buttons and show completion
      # 메시지 타임스탬프 가져오기 (슬래시 커맨드 vs 일반 메시지)
      message_ts = body.get("message", {}).get("ts") or body.get("container",
                                                                 {}).get(
          "message_ts")
      channel_id = body["channel"]["id"]

      completion_blocks = [
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": completion_text
          }
        }
      ]

      if message_ts:
        try:
          # 메시지 업데이트 시도
          await client.chat_update(
              channel=channel_id,
              ts=message_ts,
              text=completion_text,
              blocks=completion_blocks
          )
        except Exception as update_error:
          logger.warning(f"⚠️ 메시지 업데이트 실패, 새 메시지 발송: {update_error}")
          # 업데이트 실패 시 새 메시지 발송
          await client.chat_postMessage(
              channel=channel_id,
              text=completion_text,
              blocks=completion_blocks
          )
      else:
        # 메시지 타임스탬프가 없으면 새 메시지 발송
        await client.chat_postMessage(
            channel=channel_id,
            text=completion_text,
            blocks=completion_blocks
        )

    except Exception as e:
      logger.error(f"❌ Failed to record wake-up: {e}")
      # Send error as ephemeral message
      await client.chat_postEphemeral(
          channel=body["channel"]["id"],
          user=user_id,
          text=f"❌ 기록 실패: {str(e)}"
      )

  @app.view("work_log_feedback_modal")
  async def handle_work_log_feedback_submission(ack, body, client, view,
      logger):
    """Handle work log feedback modal submission"""

    try:
      # Extract form values
      values = view["state"]["values"]

      selected_date = values["date_block"]["work_log_date"]["selected_date"]
      feedback_flavor = \
        values["feedback_flavor_block"]["feedback_flavor"]["selected_option"][
          "value"]
      ai_provider = \
        values["ai_provider_block"]["ai_provider"]["selected_option"]["value"]

      user_id = body["user"]["id"]

      # Get database_id from user mapping
      database_mapping_str = os.getenv("NOTION_WORK_DATABASE_MAPPING", "{}")
      try:
        database_mapping = json.loads(database_mapping_str)
      except json.JSONDecodeError:
        logger.error(f"❌ Failed to parse NOTION_WORK_DATABASE_MAPPING")
        database_mapping = {}

      database_id = database_mapping.get(user_id)

      if not database_id:
        logger.error(f"❌ No database mapping found for user: {user_id}")
        await ack()
        await client.chat_postMessage(
            channel=REPORT_CHANNEL_ID,
            text=f"<@{user_id}>님의 업무일지 데이터베이스를 찾을 수 없습니다.\n"
                 f"관리자에게 문의하세요. (User ID: {user_id})"
        )
        return

      logger.info(
          f"📝 Processing work log feedback: date={selected_date}, "
          f"flavor={feedback_flavor}, ai={ai_provider}, db={database_id}"
      )

      # Acknowledge modal submission immediately
      await ack()

      # Send work log feedback messages to the report channel
      channel_id = REPORT_CHANNEL_ID

      try:
        # Get work log manager upfront so initial AI label can reflect dynamic provider later
        work_log_mgr = get_work_log_manager(ai_provider_type=ai_provider)
        # 이전 작업 잔여 상태 초기화 (초기 메시지 표기 안정화)
        try:
          work_log_mgr.last_used_ai_provider = None
        except Exception:
          pass
        used_ai_label = get_used_ai_label(work_log_mgr, ai_provider)

        # Send initial progress message with dynamic AI label
        progress_msg = await client.chat_postMessage(
            channel=channel_id,
            text=build_initial_text(
              user_mention=f"<@{user_id}>님의 ",
              date=selected_date,
              ai_label=used_ai_label,
              flavor_line=f"{flavor_emoji(feedback_flavor)} 피드백: {flavor_label(feedback_flavor)}",
            )
        )

        msg_ts = progress_msg["ts"]

        # Update: Finding work log
        used_ai_now = get_used_ai_label(work_log_mgr, ai_provider)
        await client.chat_update(
            channel=channel_id,
            ts=msg_ts,
            text=build_progress_text(
              user_mention=f"<@{user_id}>님의 ",
              date=selected_date,
              ai_label=used_ai_now,
              flavor_line=f"{flavor_emoji(feedback_flavor)} 피드백: {flavor_label(feedback_flavor)}",
              status="업무일지 확인 중...",
            )
        )

        # Progress updater that reflects fallback provider if it occurs
        async def progress_update(status: str):
          used_ai_dyn = get_used_ai_label(work_log_mgr, ai_provider)
          return await client.chat_update(
              channel=channel_id,
              ts=msg_ts,
              text=build_progress_text(
                user_mention=f"<@{user_id}>님의 ",
                date=selected_date,
                ai_label=used_ai_dyn,
                flavor_line=f"{flavor_emoji(feedback_flavor)} 피드백: {flavor_label(feedback_flavor)}",
                status=status,
              )
          )

        # Process feedback with progress updates
        result = await work_log_mgr.process_feedback(
            date=selected_date,
            database_id=database_id,
            flavor=feedback_flavor,
            progress_callback=progress_update
        )

        # Update with final success message
        used_ai = (result.get('used_ai_provider') if isinstance(result, dict) else None) or ai_provider
        success_text = (
          f"<@{user_id}>님의 업무일지 AI 피드백 생성 완료! ✅\n\n"
          f"📅 날짜: {selected_date}\n"
          f"{flavor_emoji(feedback_flavor)} 피드백: {flavor_label(feedback_flavor)}\n"
          f"🤖 AI: {used_ai.upper()}\n"
          f"📝 피드백 길이: {result['feedback_length']}자\n\n"
          f"✨ Notion 페이지에서 확인하세요!"
        )

        await client.chat_update(
            channel=channel_id,
            ts=msg_ts,
            text=success_text
        )

        # 스레드에 생성된 피드백 전문 게시
        try:
          from ..common.slack_utils import split_text_for_slack
          feedback_text = result.get('feedback') if isinstance(result, dict) else None
          if feedback_text:
            header = (
              f"🧵 AI 피드백 전문\n"
              f"🤖 AI: {used_ai} | {flavor_emoji(feedback_flavor)} 피드백: {flavor_label(feedback_flavor)}\n\n"
            )
            combined = header + feedback_text
            for chunk in split_text_for_slack(combined):
              await client.chat_postMessage(
                  channel=channel_id,
                  thread_ts=msg_ts,
                  text=chunk
              )
        except Exception as e:
          logger.warning(f"⚠️ 스레드에 피드백 전문 게시 실패: {e}")

        logger.info(f"✅ Work log feedback completed: {selected_date}")

      except ValueError as ve:
        # Handle validation errors (page not found, already completed)
        error_text = (
          f"<@{user_id}>님의 업무일지 피드백 생성 실패 ⚠️\n\n"
          f"📅 날짜: {selected_date}\n"
          f"❌ 오류: {str(ve)}"
        )

        await client.chat_update(
            channel=channel_id,
            ts=msg_ts,
            text=error_text
        )
        logger.warning(f"⚠️ Validation error: {ve}")

      except Exception as e:
        # Handle other errors
        used_ai = (getattr(work_log_mgr, 'last_used_ai_provider', None) or ai_provider).upper()
        error_text = (
          f"<@{user_id}>님의 업무일지 피드백 생성 실패 ❌\n\n"
          f"📅 날짜: {selected_date}\n"
          f"{flavor_emoji(feedback_flavor)} 피드백: {flavor_label(feedback_flavor)}\n"
          f"🤖 AI: {used_ai}\n"
          f"❌ 오류: {str(e)}\n\n"
          f"로그를 확인하거나 다시 시도해주세요."
        )

        await client.chat_update(
            channel=channel_id,
            ts=msg_ts,
            text=error_text
        )

        logger.error(f"❌ Failed to process feedback: {e}", exc_info=True)

    except Exception as e:
      logger.error(f"❌ Modal submission handler failed: {e}", exc_info=True)
      # Cannot send message here as we don't have channel context
      await ack(
          response_action="errors",
          errors={"date_block": "처리 중 오류가 발생했습니다. 다시 시도해주세요."}
      )
