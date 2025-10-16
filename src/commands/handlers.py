"""Slash command handlers"""

import logging

logger = logging.getLogger(__name__)


def register_slash_commands(app):
  """Register all slash command handlers"""

  @app.command("/상태")
  async def handle_status_command(ack, respond):
    """Handle /status command"""
    await ack()
    await respond("저는 건강합니다! ✅")

  @app.command("/기상테스트")
  async def handle_morning_test_command(ack, respond, logger):
    """Handle /기상테스트 command - Send test morning message"""
    await ack()

    try:
      logger.info("🧪 Morning test message command triggered")

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

      await respond(blocks=blocks, text="좋은 아침이에요! 오늘도 화이팅! 💪")
      logger.info("✅ Morning test message sent")

    except Exception as e:
      logger.error(f"❌ Failed to send morning test message: {e}")
      await respond(f"❌ 메시지 발송 실패: {str(e)}")
