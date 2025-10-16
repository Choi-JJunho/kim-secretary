"""Chat message event handlers"""

import logging
from datetime import datetime

import pytz

from ..notion.wake_up import get_wake_up_manager

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


def register_chat_handlers(app):
  """Register all chat-related event handlers"""


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
      message_ts = body.get("message", {}).get("ts") or body.get("container", {}).get("message_ts")

      if message_ts:
        await client.chat_update(
            channel=body["channel"]["id"],
            ts=message_ts,
            text=completion_text,
            blocks=[
              {
                "type": "section",
                "text": {
                  "type": "mrkdwn",
                  "text": completion_text
                }
              }
            ]
        )
      else:
        # 메시지 업데이트가 불가능한 경우 새 메시지 발송
        await client.chat_postMessage(
            channel=body["channel"]["id"],
            text=completion_text,
            blocks=[
              {
                "type": "section",
                "text": {
                  "type": "mrkdwn",
                  "text": completion_text
                }
              }
            ]
        )

    except Exception as e:
      logger.error(f"❌ Failed to record wake-up: {e}")
      # Send error as ephemeral message
      await client.chat_postEphemeral(
          channel=body["channel"]["id"],
          user=user_id,
          text=f"❌ 기록 실패: {str(e)}"
      )
