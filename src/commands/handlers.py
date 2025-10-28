"""Slash command handlers"""

import logging
from datetime import datetime

import pytz

from ..common.slack_modal_builder import (
  create_work_log_feedback_modal,
  create_weekly_report_modal,
  create_monthly_report_modal
)

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


def register_slash_commands(app):
  """Register all slash command handlers"""

  @app.command("/상태")
  async def handle_status_command(ack, respond):
    """Handle /status command"""
    await ack()
    await respond("저는 건강합니다! ✅")

  @app.command("/기상테스트")
  async def handle_morning_test_command(ack, respond, client, body, logger):
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

      # 채널에 public 메시지로 발송 (업데이트 가능하도록)
      channel_id = body.get("channel_id")
      await client.chat_postMessage(
          channel=channel_id,
          blocks=blocks,
          text="좋은 아침이에요! 오늘도 화이팅! 💪"
      )

      # 사용자에게는 확인 메시지만 ephemeral로
      await respond("✅ 테스트 메시지를 발송했습니다!", response_type="ephemeral")
      logger.info("✅ Morning test message sent")

    except Exception as e:
      logger.error(f"❌ Failed to send morning test message: {e}")
      await respond(f"❌ 메시지 발송 실패: {str(e)}")

  @app.command("/업무일지피드백")
  async def handle_work_log_feedback_command(ack, body, client):
    """Handle /업무일지피드백 command - Open modal for date selection"""
    try:
      logger.info("📝 Work log feedback command triggered")

      # Create modal view
      modal_view = create_work_log_feedback_modal(
          channel_id=body.get("channel_id"),
          user_id=body.get("user_id")
      )

      await client.views_open(
          trigger_id=body["trigger_id"],
          view=modal_view
      )

      # Acknowledge after modal is opened
      await ack()
      logger.info("✅ Work log feedback modal opened")

    except Exception as e:
      logger.error(f"❌ Failed to open modal: {e}")
      await ack(text=f"❌ 모달 열기 실패: {str(e)}")

  @app.command("/주간리포트")
  async def handle_weekly_report_command(ack, body, client):
    """Handle /주간리포트 command - Open modal for week selection"""
    try:
      logger.info("📅 Weekly report command triggered")

      # Create modal view
      modal_view = create_weekly_report_modal(
          channel_id=body.get("channel_id"),
          user_id=body.get("user_id")
      )

      await client.views_open(
          trigger_id=body["trigger_id"],
          view=modal_view
      )

      await ack()
      logger.info("✅ Weekly report modal opened")

    except Exception as e:
      logger.error(f"❌ Failed to open modal: {e}")
      await ack(text=f"❌ 모달 열기 실패: {str(e)}")

  @app.command("/월간리포트")
  async def handle_monthly_report_command(ack, body, client):
    """Handle /월간리포트 command - Open modal for month selection"""
    try:
      logger.info("📅 Monthly report command triggered")

      # Create modal view
      modal_view = create_monthly_report_modal(
          channel_id=body.get("channel_id"),
          user_id=body.get("user_id")
      )

      await client.views_open(
          trigger_id=body["trigger_id"],
          view=modal_view
      )

      await ack()
      logger.info("✅ Monthly report modal opened")

    except Exception as e:
      logger.error(f"❌ Failed to open modal: {e}")
      await ack(text=f"❌ 모달 열기 실패: {str(e)}")
