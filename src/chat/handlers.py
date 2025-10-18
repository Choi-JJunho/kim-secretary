"""Chat message event handlers"""

import logging
import os
from datetime import datetime

import pytz

from ..notion.wake_up import get_wake_up_manager
from ..notion.work_log_agent import get_work_log_manager
from ..commands.work_log_webhook_handler import (
    handle_work_log_webhook_message,
    parse_work_log_message
)

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')

# Webhook channel ID
WEBHOOK_CHANNEL_ID = os.getenv("SLACK_WORK_LOG_WEBHOOK_CHANNEL_ID")


def register_chat_handlers(app):
  """Register all chat-related event handlers"""

  @app.event("message")
  async def handle_message_events(event, say, client):
    """Handle all message events"""
    # Ignore bot messages and message subtypes
    if event.get("subtype") is not None:
      return

    # Check if this is a work log webhook message
    channel_id = event.get("channel")
    if channel_id == WEBHOOK_CHANNEL_ID:
      message_text = event.get("text", "")
      if parse_work_log_message(message_text):
        # Handle work log webhook message
        await handle_work_log_webhook_message(event, say, client)
        return

    # Handle other message types here if needed
    # For now, just ignore other messages
    pass

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

      logger.info(
          f"📝 Processing work log feedback: date={selected_date}, "
          f"flavor={feedback_flavor}, ai={ai_provider}"
      )

      # Acknowledge modal submission immediately
      await ack()

      # Get channel from trigger (modal was opened from a channel)
      # Use the channel where the command was triggered
      channel_id = None

      # Try to get channel from various possible locations
      if "view" in body and "private_metadata" in body["view"]:
        # If we stored it in private_metadata
        import json
        try:
          metadata = json.loads(body["view"]["private_metadata"])
          channel_id = metadata.get("channel_id")
        except:
          pass

      # Fallback: send to a default channel or user's DM
      if not channel_id:
        # Send to user's DM instead
        dm_response = await client.conversations_open(users=[user_id])
        channel_id = dm_response["channel"]["id"]

      # Flavor emoji mapping
      flavor_emoji = {
        "spicy": "🔥",
        "normal": "🌶️",
        "mild": "🍀"
      }
      flavor_name = {
        "spicy": "매운맛",
        "normal": "보통맛",
        "mild": "순한맛"
      }

      try:
        # Send initial progress message with user mention
        progress_msg = await client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}>님의 업무일지 피드백을 생성중입니다...\n\n"
                 f"📅 날짜: {selected_date}\n"
                 f"{flavor_emoji.get(feedback_flavor, '🌶️')} 피드백: {flavor_name.get(feedback_flavor, '보통맛')}\n"
                 f"🤖 AI: {ai_provider.upper()}\n"
                 f"⏳ 상태: 업무일지 검색 중..."
        )

        msg_ts = progress_msg["ts"]

        # Get work log manager with selected AI provider
        work_log_mgr = get_work_log_manager(ai_provider_type=ai_provider)

        # Update: Finding work log
        await client.chat_update(
            channel=channel_id,
            ts=msg_ts,
            text=f"<@{user_id}>님의 업무일지 피드백을 생성중입니다...\n\n"
                 f"📅 날짜: {selected_date}\n"
                 f"{flavor_emoji.get(feedback_flavor, '🌶️')} 피드백: {flavor_name.get(feedback_flavor, '보통맛')}\n"
                 f"🤖 AI: {ai_provider.upper()}\n"
                 f"⏳ 상태: 업무일지 확인 중..."
        )

        # Process feedback with progress updates
        result = await work_log_mgr.process_feedback(
            selected_date,
            flavor=feedback_flavor,
            progress_callback=lambda status: client.chat_update(
                channel=channel_id,
                ts=msg_ts,
                text=f"<@{user_id}>님의 업무일지 피드백을 생성중입니다...\n\n"
                     f"📅 날짜: {selected_date}\n"
                     f"{flavor_emoji.get(feedback_flavor, '🌶️')} 피드백: {flavor_name.get(feedback_flavor, '보통맛')}\n"
                     f"🤖 AI: {ai_provider.upper()}\n"
                     f"⏳ 상태: {status}"
            )
        )

        # Update with final success message
        success_text = (
          f"<@{user_id}>님의 업무일지 AI 피드백 생성 완료! ✅\n\n"
          f"📅 날짜: {selected_date}\n"
          f"{flavor_emoji.get(feedback_flavor, '🌶️')} 피드백: {flavor_name.get(feedback_flavor, '보통맛')}\n"
          f"🤖 AI: {ai_provider.upper()}\n"
          f"📝 피드백 길이: {result['feedback_length']}자\n\n"
          f"✨ Notion 페이지에서 확인하세요!"
        )

        await client.chat_update(
            channel=channel_id,
            ts=msg_ts,
            text=success_text
        )

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
        error_text = (
          f"<@{user_id}>님의 업무일지 피드백 생성 실패 ❌\n\n"
          f"📅 날짜: {selected_date}\n"
          f"{flavor_emoji.get(feedback_flavor, '🌶️')} 피드백: {flavor_name.get(feedback_flavor, '보통맛')}\n"
          f"🤖 AI: {ai_provider.upper()}\n"
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
