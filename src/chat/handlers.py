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
from ..notion.weekly_report_agent import get_weekly_report_manager
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

      # Get database_id from unified user mapping
      user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")
      try:
        user_db_mapping = json.loads(user_db_mapping_str)
      except json.JSONDecodeError:
        logger.error(f"❌ Failed to parse NOTION_USER_DATABASE_MAPPING")
        user_db_mapping = {}

      user_dbs = user_db_mapping.get(user_id, {})
      database_id = user_dbs.get("work_log_db")

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

  @app.view("weekly_report_modal")
  async def handle_weekly_report_submission(ack, body, client, view, logger):
    """Handle weekly report modal submission"""

    try:
      # Extract form values
      values = view["state"]["values"]

      year = int(values["year_block"]["report_year"]["value"])
      week = int(values["week_block"]["report_week"]["value"])
      ai_provider = values["ai_provider_block"]["ai_provider"]["selected_option"]["value"]

      user_id = body["user"]["id"]

      # Get database mappings from unified user mapping
      user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")
      try:
        user_db_mapping = json.loads(user_db_mapping_str)
      except json.JSONDecodeError:
        logger.error(f"❌ Failed to parse NOTION_USER_DATABASE_MAPPING")
        user_db_mapping = {}

      user_dbs = user_db_mapping.get(user_id, {})

      if not user_dbs:
        logger.error(f"❌ No database mapping found for user: {user_id}")
        await ack()
        await client.chat_postMessage(
            channel=REPORT_CHANNEL_ID,
            text=f"<@{user_id}>님의 데이터베이스 매핑을 찾을 수 없습니다.\n"
                 f"관리자에게 문의하세요. (User ID: {user_id})"
        )
        return

      work_log_db_id = user_dbs.get("work_log_db")
      weekly_report_db_id = user_dbs.get("weekly_report_db")

      if not work_log_db_id or not weekly_report_db_id:
        logger.error(f"❌ Incomplete database mapping for user: {user_id}")
        await ack()
        await client.chat_postMessage(
            channel=REPORT_CHANNEL_ID,
            text=f"<@{user_id}>님의 데이터베이스 설정이 불완전합니다.\n"
                 f"관리자에게 문의하세요."
        )
        return

      logger.info(
          f"📅 Processing weekly report: year={year}, week={week}, "
          f"ai={ai_provider}, user={user_id}"
      )

      # Acknowledge modal submission immediately
      await ack()

      # Send to report channel
      channel_id = REPORT_CHANNEL_ID

      try:
        # Get weekly report manager
        weekly_mgr = get_weekly_report_manager(ai_provider_type=ai_provider)

        # Send initial progress message
        progress_msg = await client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}>님의 주간 리포트 생성 중... 📅\n\n"
                 f"📆 기간: {year}-W{week:02d}\n"
                 f"🤖 AI: {ai_provider.upper()}\n"
                 f"⏳ 진행 중..."
        )

        msg_ts = progress_msg["ts"]

        # Progress updater
        async def progress_update(status: str):
          used_ai_label = (weekly_mgr.last_used_ai_provider or ai_provider).upper()
          return await client.chat_update(
              channel=channel_id,
              ts=msg_ts,
              text=f"<@{user_id}>님의 주간 리포트 생성 중... 📅\n\n"
                   f"📆 기간: {year}-W{week:02d}\n"
                   f"🤖 AI: {used_ai_label}\n"
                   f"⏳ {status}"
          )

        # Generate weekly report with progress updates
        result = await weekly_mgr.generate_weekly_report(
            year=year,
            week=week,
            work_log_database_id=work_log_db_id,
            weekly_report_database_id=weekly_report_db_id,
            progress_callback=progress_update
        )

        # Update with final success message
        used_ai = result.get('used_ai_provider', ai_provider).upper()
        daily_logs_count = result.get('daily_logs_count', 0)
        page_url = result.get('page_url', '')

        success_text = (
          f"<@{user_id}>님의 주간 리포트 생성 완료! ✅\n\n"
          f"📆 기간: {year}-W{week:02d}\n"
          f"🤖 AI: {used_ai}\n"
          f"📊 분석한 업무일지: {daily_logs_count}개\n\n"
          f"✨ Notion에서 확인하세요!"
        )

        if page_url:
          success_text += f"\n🔗 <{page_url}|리포트 바로가기>"

        await client.chat_update(
            channel=channel_id,
            ts=msg_ts,
            text=success_text
        )

        # Post analysis preview in thread
        try:
          analysis = result.get('analysis', '')
          if analysis and isinstance(analysis, str):
            # 마크다운 텍스트의 미리보기 (처음 1000자)
            preview_length = 1000
            if len(analysis) > preview_length:
              preview = analysis[:preview_length] + f"\n\n... (총 {len(analysis)}자)\n\n"
            else:
              preview = analysis

            thread_text = f"🧵 주간 리포트 미리보기\n\n{preview}\n자세한 내용은 Notion 페이지에서 확인하세요!"

            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=msg_ts,
                text=thread_text
            )
        except Exception as e:
          logger.warning(f"⚠️ 스레드에 미리보기 게시 실패: {e}")

        logger.info(f"✅ Weekly report completed: {year}-W{week:02d}")

      except ValueError as ve:
        # Handle validation errors
        error_text = (
          f"<@{user_id}>님의 주간 리포트 생성 실패 ⚠️\n\n"
          f"📆 기간: {year}-W{week:02d}\n"
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
          f"<@{user_id}>님의 주간 리포트 생성 실패 ❌\n\n"
          f"📆 기간: {year}-W{week:02d}\n"
          f"🤖 AI: {ai_provider.upper()}\n"
          f"❌ 오류: {str(e)}\n\n"
          f"로그를 확인하거나 다시 시도해주세요."
        )

        await client.chat_update(
            channel=channel_id,
            ts=msg_ts,
            text=error_text
        )

        logger.error(f"❌ Failed to generate weekly report: {e}", exc_info=True)

    except Exception as e:
      logger.error(f"❌ Modal submission handler failed: {e}", exc_info=True)
      await ack(
          response_action="errors",
          errors={"year_block": "처리 중 오류가 발생했습니다. 다시 시도해주세요."}
      )

  @app.view("monthly_report_modal")
  async def handle_monthly_report_submission(ack, body, client, view, logger):
    """Handle monthly report modal submission"""
    try:
      logger.info("📝 Monthly report modal submitted")

      # Extract form values
      values = view["state"]["values"]
      year = int(values["year_block"]["report_year"]["value"])
      month = int(values["month_block"]["report_month"]["value"])
      ai_provider = values["ai_provider_block"]["ai_provider"]["selected_option"]["value"]

      user_id = body["user"]["id"]

      # Get database mappings from unified user mapping
      user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")
      try:
        user_db_mapping = json.loads(user_db_mapping_str)
      except json.JSONDecodeError:
        logger.error(f"❌ Failed to parse NOTION_USER_DATABASE_MAPPING")
        user_db_mapping = {}

      user_dbs = user_db_mapping.get(user_id, {})

      if not user_dbs:
        logger.error(f"❌ No database mapping found for user: {user_id}")
        await ack()
        await client.chat_postMessage(
            channel=REPORT_CHANNEL_ID,
            text=f"<@{user_id}>님의 데이터베이스 매핑을 찾을 수 없습니다.\n"
                 f"관리자에게 문의하세요. (User ID: {user_id})"
        )
        return

      weekly_report_db_id = user_dbs.get("weekly_report_db")
      monthly_report_db_id = user_dbs.get("monthly_report_db")

      if not weekly_report_db_id or not monthly_report_db_id:
        logger.error(f"❌ Incomplete database mapping for user: {user_id}")
        await ack()
        await client.chat_postMessage(
            channel=REPORT_CHANNEL_ID,
            text=f"<@{user_id}>님의 데이터베이스 설정이 불완전합니다.\n"
                 f"주간/월간 리포트 DB를 모두 설정해주세요."
        )
        return

      logger.info(
          f"✅ Database mapping found: weekly={weekly_report_db_id}, monthly={monthly_report_db_id}")

      # Acknowledge modal
      await ack()

      # Get channel from private_metadata
      private_metadata = json.loads(view.get("private_metadata", "{}"))
      channel_id = private_metadata.get(
          "channel_id") or body.get("channel_id") or REPORT_CHANNEL_ID

      # Post initial message
      msg_response = await client.chat_postMessage(
          channel=channel_id,
          text=f"📅 {year}년 {month}월 월간 리포트 생성을 시작합니다... (AI: {ai_provider.upper()})"
      )
      msg_ts = msg_response["ts"]

      # Progress callback
      async def progress_callback(status: str):
        try:
          await client.chat_update(
              channel=channel_id,
              ts=msg_ts,
              text=status
          )
        except Exception as e:
          logger.warning(f"⚠️ Failed to update progress: {e}")

      # Generate monthly report
      from ..notion.monthly_report_agent import get_monthly_report_manager

      try:
        monthly_mgr = get_monthly_report_manager(ai_provider_type=ai_provider)
        result = await monthly_mgr.generate_monthly_report(
            year=year,
            month=month,
            weekly_report_database_id=weekly_report_db_id,
            monthly_report_database_id=monthly_report_db_id,
            progress_callback=progress_callback
        )

        # Update message with success
        page_url = result.get('page_url', '')
        used_provider = result.get('used_ai_provider', ai_provider).upper()
        weekly_count = result.get('weekly_reports_count', 0)

        success_text = (
            f"✅ {year}년 {month}월 월간 리포트 생성 완료!\n\n"
            f"🤖 AI: {used_provider}\n"
            f"📊 분석한 주간 리포트: {weekly_count}개"
        )

        if page_url:
          success_text += f"\n🔗 <{page_url}|리포트 바로가기>"

        await client.chat_update(
            channel=channel_id,
            ts=msg_ts,
            text=success_text
        )

        # Post analysis preview in thread
        try:
          analysis = result.get('analysis', '')
          if analysis and isinstance(analysis, str):
            # 마크다운 텍스트의 미리보기 (처음 1000자)
            preview_length = 1000
            if len(analysis) > preview_length:
              preview = analysis[:preview_length] + f"\n\n... (총 {len(analysis)}자)\n\n"
            else:
              preview = analysis

            thread_text = f"🧵 월간 리포트 미리보기\n\n{preview}\n자세한 내용은 <{page_url}|Notion 페이지>에서 확인하세요!"

            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=msg_ts,
                text=thread_text
            )

        except Exception as e:
          logger.warning(f"⚠️ 스레드에 미리보기 게시 실패: {e}")

        logger.info(
            f"✅ Monthly report generated successfully: {year}-{month:02d}")

      except Exception as e:
        error_text = (
          f"❌ 월간 리포트 생성 실패\n\n"
          f"📅 기간: {year}년 {month}월\n"
          f"❌ 오류: {str(e)}\n\n"
          f"로그를 확인하거나 다시 시도해주세요."
        )

        await client.chat_update(
            channel=channel_id,
            ts=msg_ts,
            text=error_text
        )

        logger.error(f"❌ Failed to generate monthly report: {e}", exc_info=True)

    except Exception as e:
      logger.error(f"❌ Modal submission handler failed: {e}", exc_info=True)
      await ack(
          response_action="errors",
          errors={"year_block": "처리 중 오류가 발생했습니다. 다시 시도해주세요."}
      )
