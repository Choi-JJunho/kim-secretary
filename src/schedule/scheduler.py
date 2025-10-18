"""스케줄러 - 매일 아침 메시지 발송"""

import logging
import os

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# KST 시간대
KST = pytz.timezone('Asia/Seoul')


class MorningScheduler:
  """아침 메시지 스케줄러"""

  def __init__(self, app):
    """
    스케줄러 초기화

    Args:
        app: Slack AsyncApp 인스턴스
    """
    self.app = app
    self.scheduler = AsyncIOScheduler(timezone=KST)
    self.channel_id = os.getenv("SLACK_WAKE_UP_CHANNEL_ID")

    if not self.channel_id:
      raise ValueError("SLACK_WAKE_UP_CHANNEL_ID 환경 변수가 설정되지 않았습니다")

    # 매일 아침 6시 30분 스케줄 등록
    self.scheduler.add_job(
        self.send_morning_message,
        trigger=CronTrigger(
            hour=6,
            minute=30,
            timezone=KST
        ),
        id='morning_message',
        name='아침 기상 메시지',
        replace_existing=True
    )

    logger.info("✅ 아침 메시지 스케줄 등록 완료 (매일 6:30 AM)")

  def start(self):
    """스케줄러 시작"""
    if not self.scheduler.running:
      self.scheduler.start()
      logger.info("🚀 스케줄러 시작")

  def stop(self):
    """스케줄러 중지"""
    if self.scheduler.running:
      self.scheduler.shutdown()
      logger.info("⏹️ 스케줄러 중지")

  async def send_morning_message(self):
    """아침 메시지 발송"""
    try:
      logger.info("🌅 아침 메시지 발송 시작")

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

      await self.app.client.chat_postMessage(
          channel=self.channel_id,
          blocks=blocks,
          text="좋은 아침이에요! 오늘도 화이팅! 💪"
      )

      logger.info("✅ 아침 메시지 발송 완료")

    except Exception as e:
      logger.error(f"❌ 아침 메시지 발송 실패: {e}")


def get_scheduler(app):
  """스케줄러 인스턴스 생성"""
  return MorningScheduler(app)
