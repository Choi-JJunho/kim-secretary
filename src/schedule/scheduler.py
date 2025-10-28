"""스케줄러 - 매일 아침 메시지 발송 및 주간/월간 리포트 자동 생성"""

import json
import logging
import os
from calendar import monthrange
from datetime import datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# KST 시간대
KST = pytz.timezone('Asia/Seoul')


class MorningScheduler:
  """아침 메시지 및 리포트 생성 스케줄러"""

  def __init__(self, app):
    """
    스케줄러 초기화

    Args:
        app: Slack AsyncApp 인스턴스
    """
    self.app = app
    self.scheduler = AsyncIOScheduler(timezone=KST)
    self.wake_up_channel_id = os.getenv("SLACK_WAKE_UP_CHANNEL_ID")
    self.report_channel_id = os.getenv("SLACK_REPORT_CHANNEL_ID")

    if not self.wake_up_channel_id:
      raise ValueError("SLACK_WAKE_UP_CHANNEL_ID 환경 변수가 설정되지 않았습니다")

    if not self.report_channel_id:
      raise ValueError("SLACK_REPORT_CHANNEL_ID 환경 변수가 설정되지 않았습니다")

    # 매일 아침 6시 30분: 기상 메시지
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

    # 매주 금요일 오후 10시: 주간 리포트 자동 생성
    self.scheduler.add_job(
        self.generate_weekly_reports,
        trigger=CronTrigger(
            day_of_week='fri',
            hour=22,
            minute=0,
            timezone=KST
        ),
        id='weekly_report',
        name='주간 리포트 자동 생성',
        replace_existing=True
    )

    # 매월 1일 오후 10시: 월간 리포트 자동 생성
    self.scheduler.add_job(
        self.generate_monthly_reports,
        trigger=CronTrigger(
            day='1',
            hour=22,
            minute=0,
            timezone=KST
        ),
        id='monthly_report',
        name='월간 리포트 자동 생성',
        replace_existing=True
    )

    logger.info("✅ 스케줄 등록 완료")
    logger.info("  - 아침 기상 메시지: 매일 6:30 AM")
    logger.info("  - 주간 리포트: 매주 금요일 10:00 PM")
    logger.info("  - 월간 리포트: 매월 1일 10:00 PM")

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
          channel=self.wake_up_channel_id,
          blocks=blocks,
          text="좋은 아침이에요! 오늘도 화이팅! 💪"
      )

      logger.info("✅ 아침 메시지 발송 완료")

    except Exception as e:
      logger.error(f"❌ 아침 메시지 발송 실패: {e}")

  async def generate_weekly_reports(self):
    """주간 리포트 자동 생성 (모든 유저)"""
    try:
      logger.info("📅 주간 리포트 자동 생성 시작")

      # Get current week
      now = datetime.now(KST)
      year = now.year
      week = now.isocalendar()[1]

      # Get user database mapping
      user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")
      try:
        user_db_mapping = json.loads(user_db_mapping_str)
      except json.JSONDecodeError:
        logger.error("❌ Failed to parse NOTION_USER_DATABASE_MAPPING")
        return

      if not user_db_mapping:
        logger.warning("⚠️ No user database mapping found")
        return

      # Import manager
      from ..notion.weekly_report_agent import get_weekly_report_manager

      # Generate reports for each user
      for user_id, user_dbs in user_db_mapping.items():
        try:
          user_alias = user_dbs.get("alias", "이름없음")
          work_log_db = user_dbs.get("work_log_db")
          weekly_report_db = user_dbs.get("weekly_report_db")
          resume_page = user_dbs.get("resume_page")

          if not work_log_db or not weekly_report_db:
            logger.warning(f"⚠️ Incomplete DB mapping for {user_alias} ({user_id})")
            continue

          logger.info(f"📊 Generating weekly report for {user_alias}...")

          # Send initial message
          msg = await self.app.client.chat_postMessage(
              channel=self.report_channel_id,
              text=f"⏳ <@{user_id}>님의 {year}-W{week:02d} 주간 리포트 생성 중..."
          )
          msg_ts = msg["ts"]

          # Progress callback
          async def progress_update(status: str):
            await self.app.client.chat_update(
                channel=self.report_channel_id,
                ts=msg_ts,
                text=f"⏳ <@{user_id}>님의 {year}-W{week:02d} 주간 리포트 생성 중...\n📍 {status}"
            )

          # Generate report
          manager = get_weekly_report_manager(ai_provider_type="claude")
          result = await manager.generate_weekly_report(
              year=year,
              week=week,
              work_log_database_id=work_log_db,
              weekly_report_database_id=weekly_report_db,
              progress_callback=progress_update,
              resume_page_id=resume_page
          )

          # Update with success message
          page_url = result.get('page_url', '')
          daily_count = result.get('daily_logs_count', 0)
          used_provider = result.get('used_ai_provider', 'CLAUDE').upper()

          success_text = (
              f"✅ <@{user_id}>님의 {year}-W{week:02d} 주간 리포트 생성 완료!\n\n"
              f"🤖 AI: {used_provider}\n"
              f"📊 분석한 업무일지: {daily_count}개"
          )

          if page_url:
            success_text += f"\n🔗 <{page_url}|리포트 바로가기>"

          await self.app.client.chat_update(
              channel=self.report_channel_id,
              ts=msg_ts,
              text=success_text
          )

          logger.info(f"✅ Weekly report generated for {user_alias}")

        except Exception as e:
          logger.error(f"❌ Failed to generate weekly report for {user_alias}: {e}")
          try:
            await self.app.client.chat_postMessage(
                channel=self.report_channel_id,
                text=f"❌ <@{user_id}>님의 주간 리포트 생성 실패\n오류: {str(e)}"
            )
          except:
            pass

      logger.info("✅ 주간 리포트 자동 생성 완료")

    except Exception as e:
      logger.error(f"❌ 주간 리포트 자동 생성 실패: {e}", exc_info=True)

  async def generate_monthly_reports(self):
    """월간 리포트 자동 생성 (모든 유저)"""
    try:
      logger.info("📅 월간 리포트 자동 생성 시작")

      # Get current month
      now = datetime.now(KST)
      year = now.year
      month = now.month

      # Get user database mapping
      user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")
      try:
        user_db_mapping = json.loads(user_db_mapping_str)
      except json.JSONDecodeError:
        logger.error("❌ Failed to parse NOTION_USER_DATABASE_MAPPING")
        return

      if not user_db_mapping:
        logger.warning("⚠️ No user database mapping found")
        return

      # Import manager
      from ..notion.monthly_report_agent import get_monthly_report_manager

      # Generate reports for each user
      for user_id, user_dbs in user_db_mapping.items():
        try:
          user_alias = user_dbs.get("alias", "이름없음")
          weekly_report_db = user_dbs.get("weekly_report_db")
          monthly_report_db = user_dbs.get("monthly_report_db")
          resume_page = user_dbs.get("resume_page")

          if not weekly_report_db or not monthly_report_db:
            logger.warning(f"⚠️ Incomplete DB mapping for {user_alias} ({user_id})")
            continue

          logger.info(f"📊 Generating monthly report for {user_alias}...")

          # Send initial message
          msg = await self.app.client.chat_postMessage(
              channel=self.report_channel_id,
              text=f"⏳ <@{user_id}>님의 {year}-{month:02d} 월간 리포트 생성 중..."
          )
          msg_ts = msg["ts"]

          # Progress callback
          async def progress_update(status: str):
            await self.app.client.chat_update(
                channel=self.report_channel_id,
                ts=msg_ts,
                text=f"⏳ <@{user_id}>님의 {year}-{month:02d} 월간 리포트 생성 중...\n📍 {status}"
            )

          # Generate report
          manager = get_monthly_report_manager(ai_provider_type="claude")
          result = await manager.generate_monthly_report(
              year=year,
              month=month,
              weekly_report_database_id=weekly_report_db,
              monthly_report_database_id=monthly_report_db,
              progress_callback=progress_update,
              resume_page_id=resume_page
          )

          # Update with success message
          page_url = result.get('page_url', '')
          weekly_count = result.get('weekly_reports_count', 0)
          used_provider = result.get('used_ai_provider', 'CLAUDE').upper()

          success_text = (
              f"✅ <@{user_id}>님의 {year}-{month:02d} 월간 리포트 생성 완료!\n\n"
              f"🤖 AI: {used_provider}\n"
              f"📊 분석한 주간 리포트: {weekly_count}개"
          )

          if page_url:
            success_text += f"\n🔗 <{page_url}|리포트 바로가기>"

          await self.app.client.chat_update(
              channel=self.report_channel_id,
              ts=msg_ts,
              text=success_text
          )

          logger.info(f"✅ Monthly report generated for {user_alias}")

        except Exception as e:
          logger.error(f"❌ Failed to generate monthly report for {user_alias}: {e}")
          try:
            await self.app.client.chat_postMessage(
                channel=self.report_channel_id,
                text=f"❌ <@{user_id}>님의 월간 리포트 생성 실패\n오류: {str(e)}"
            )
          except:
            pass

      logger.info("✅ 월간 리포트 자동 생성 완료")

    except Exception as e:
      logger.error(f"❌ 월간 리포트 자동 생성 실패: {e}", exc_info=True)


def get_scheduler(app):
  """스케줄러 인스턴스 생성"""
  return MorningScheduler(app)
