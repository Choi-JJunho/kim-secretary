"""Chat message event handlers"""

import logging
import re
from datetime import datetime

import pytz

from ..notion.wake_up import get_wake_up_manager

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


def register_chat_handlers(app):
  """Register all chat-related event handlers"""

  @app.message(re.compile("(기상|아침|hey)"))
  async def say_hello_regex(say, context, logger):
    """Respond to English greetings"""
    greeting = context['matches'][0]
    logger.info(f"💬 Greeting: {greeting}")

    blocks = [
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": "좋은 아침이에요! 오늘도 화이팅! 💪"
        }
      },
      {
        "type": "actions",
        "elements": [
          {
            "type": "button",
            "text": {
              "type": "plain_text",
              "text": "기상 완료"
            },
            "action_id": "wake_up_complete",
            "style": "primary"
          }
        ]
      }
    ]

    await say(blocks=blocks)

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
      await client.chat_update(
          channel=body["channel"]["id"],
          ts=body["message"]["ts"],
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
