"""업무일지 발행 핸들러

Notion에서 "발행" 체크박스를 클릭하면 Slack Webhook을 통해
업무일지를 junogarden-web GitHub 저장소에 발행합니다.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, Optional

from slack_bolt.async_app import AsyncApp

from ..github.junogarden_publisher import JunogardenPublisher
from ..github.portfolio_updater import get_portfolio_updater
from ..notion.client import NotionClient
from ..common.notion_utils import extract_page_content

logger = logging.getLogger(__name__)

# Webhook 채널 ID (Notion Automation에서 메시지를 받는 채널)
WEBHOOK_CHANNEL_ID = os.getenv("SLACK_WORK_LOG_WEBHOOK_CHANNEL_ID")
# 결과 리포트를 보내는 채널
REPORT_CHANNEL_ID = os.getenv("SLACK_WORK_LOG_REPORT_CHANNEL_ID")


def parse_publish_message(message_text: str) -> Optional[Dict]:
  """발행 요청 메시지 파싱

  지원하는 JSON 형식:
  {
    "action": "publish_work_log",
    "date": "2025-12-08",
    "page_id": "abc123...",
    "user_id": "U12345678",
    "update_portfolio": true
  }

  Args:
    message_text: Slack 메시지 텍스트

  Returns:
    파싱된 데이터 또는 None (파싱 실패 시)
  """
  try:
    data = json.loads(message_text.strip())
    if data.get("action") == "publish_work_log":
      return {
        "date": data.get("date"),
        "page_id": data.get("page_id"),
        "user_id": data.get("user_id"),
        "update_portfolio": data.get("update_portfolio", False)
      }
  except (json.JSONDecodeError, ValueError):
    pass
  return None


def extract_title_from_page(page: Dict) -> str:
  """Notion 페이지에서 제목 추출

  Args:
    page: Notion 페이지 객체

  Returns:
    페이지 제목 문자열
  """
  properties = page.get("properties", {})

  # 일반적인 title 속성 이름들 시도
  title_property_names = ["제목", "Title", "이름", "Name", "title", "name"]

  for prop_name in title_property_names:
    if prop_name in properties:
      prop = properties[prop_name]
      if prop.get("type") == "title":
        title_array = prop.get("title", [])
        return "".join([t.get("plain_text", "") for t in title_array])

  # properties 전체에서 title 타입 찾기
  for prop_name, prop_data in properties.items():
    if prop_data.get("type") == "title":
      title_array = prop_data.get("title", [])
      return "".join([t.get("plain_text", "") for t in title_array])

  return ""


def extract_tags_from_page(page: Dict) -> list:
  """Notion 페이지에서 태그 추출

  Args:
    page: Notion 페이지 객체

  Returns:
    태그 문자열 목록
  """
  properties = page.get("properties", {})
  tags = []

  # 일반적인 태그 속성 이름들 시도
  tag_property_names = ["기술스택", "Tags", "태그", "tags", "Tech Stack"]

  for prop_name in tag_property_names:
    if prop_name in properties:
      prop = properties[prop_name]
      if prop.get("type") == "multi_select":
        tags = [t.get("name", "") for t in prop.get("multi_select", [])]
        break
      elif prop.get("type") == "select":
        select_val = prop.get("select")
        if select_val:
          tags = [select_val.get("name", "")]
        break

  return [t for t in tags if t]  # 빈 문자열 제거


def extract_date_from_page(page: Dict, fallback_date: str) -> str:
  """Notion 페이지에서 날짜 추출

  Args:
    page: Notion 페이지 객체
    fallback_date: 찾지 못했을 때 사용할 기본 날짜

  Returns:
    YYYY-MM-DD 형식의 날짜 문자열
  """
  properties = page.get("properties", {})

  # 일반적인 날짜 속성 이름들 시도
  date_property_names = ["작성일", "Date", "날짜", "date", "Created"]

  for prop_name in date_property_names:
    if prop_name in properties:
      prop = properties[prop_name]
      if prop.get("type") == "date":
        date_obj = prop.get("date")
        if date_obj and date_obj.get("start"):
          return date_obj["start"][:10]  # YYYY-MM-DD만 추출

  return fallback_date


async def handle_publish_webhook_message(
    message: Dict,
    say,
    client
):
  """발행 Webhook 메시지 처리

  Notion Automation에서 발송된 발행 요청을 처리하여
  업무일지를 GitHub에 발행합니다.

  Args:
    message: Slack 메시지 이벤트
    say: Slack say 함수 (사용하지 않음, 호환성 유지)
    client: Slack 클라이언트
  """
  try:
    # Webhook 채널에서만 처리
    channel_id = message.get("channel")
    if channel_id != WEBHOOK_CHANNEL_ID:
      return

    # 메시지 파싱
    message_text = message.get("text", "")
    parsed = parse_publish_message(message_text)

    if not parsed:
      return  # 발행 요청이 아님

    logger.info(f"📤 Publish request received: {parsed}")

    date = parsed["date"]
    page_id = parsed["page_id"]
    user_id = parsed.get("user_id")
    update_portfolio = parsed.get("update_portfolio", False)

    # 필수 값 검증
    if not page_id:
      logger.error("❌ page_id가 없습니다")
      await client.chat_postMessage(
        channel=REPORT_CHANNEL_ID,
        text="❌ 발행 실패: page_id가 필요합니다."
      )
      return

    user_mention = f"<@{user_id}> " if user_id else ""

    # 진행 상태 메시지 발송
    status_msg = await client.chat_postMessage(
      channel=REPORT_CHANNEL_ID,
      text=f"📤 {user_mention}업무일지 발행 시작...\n📅 날짜: {date or '추출 중...'}"
    )
    message_ts = status_msg["ts"]

    try:
      # 1. Notion 페이지 내용 추출
      await client.chat_update(
        channel=REPORT_CHANNEL_ID,
        ts=message_ts,
        text=(
          f"📤 {user_mention}업무일지 발행 중...\n"
          f"📅 날짜: {date or '추출 중...'}\n\n"
          f"⏳ Notion 페이지 로드 중..."
        )
      )

      notion_client = NotionClient()
      page = await notion_client.get_page(page_id)

      # 페이지 제목 추출
      title = extract_title_from_page(page)
      if not title:
        title = f"{date} 업무일지"

      # 태그 추출
      tags = extract_tags_from_page(page)

      # 날짜 추출 (date 파라미터가 없으면 페이지에서 추출)
      if not date:
        date = extract_date_from_page(page, datetime.now().strftime("%Y-%m-%d"))

      # 날짜 형식 검증
      if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        raise ValueError(f"잘못된 날짜 형식: {date}")

      # 페이지 본문 내용 추출 (마크다운 형식)
      content = await extract_page_content(notion_client, page_id, format="markdown")

      if not content:
        raise ValueError("페이지 내용이 비어있습니다")

      logger.info(f"📄 Notion 페이지 로드 완료: {title} ({len(content)}자)")

      # 2. GitHub 발행
      await client.chat_update(
        channel=REPORT_CHANNEL_ID,
        ts=message_ts,
        text=(
          f"📤 {user_mention}업무일지 발행 중...\n"
          f"📅 날짜: {date}\n"
          f"📄 제목: {title}\n\n"
          f"⏳ GitHub에 발행 중..."
        )
      )

      publisher = JunogardenPublisher()
      result = await publisher.publish_work_log(
        date=date,
        content=content,
        title=title,
        tags=tags
      )

      if result["success"]:
        # 3. (옵션) 포트폴리오 업데이트 - Claude Code 사용
        portfolio_status = ""
        if update_portfolio:
          await client.chat_update(
            channel=REPORT_CHANNEL_ID,
            ts=message_ts,
            text=(
              f"📤 {user_mention}업무일지 발행 중...\n"
              f"📅 날짜: {date}\n"
              f"📄 제목: {title}\n\n"
              f"⏳ 포트폴리오 업데이트 중... (Claude Code)"
            )
          )

          portfolio_updater = get_portfolio_updater()
          portfolio_result = await portfolio_updater.update_portfolio(
            date=date,
            title=title,
            content=content
          )

          if portfolio_result["success"]:
            msg = portfolio_result.get("message", "완료")
            sha = portfolio_result.get("commit_sha", "")
            if sha:
              portfolio_status = f"\n📊 포트폴리오 업데이트: {msg} ({sha})"
            else:
              portfolio_status = f"\n📊 포트폴리오: {msg}"
          else:
            error = portfolio_result.get("error", "알 수 없는 오류")
            portfolio_status = f"\n⚠️ 포트폴리오 업데이트 실패: {error}"
            logger.warning(f"⚠️ Portfolio update failed: {error}")

        # 4. Notion 발행완료 체크
        try:
          await notion_client.update_page(page_id, {
            "발행완료": {"checkbox": True},
            "발행일시": {"date": {"start": datetime.now().isoformat()}}
          })
          logger.info("✅ Notion 발행완료 상태 업데이트 완료")
        except Exception as e:
          logger.warning(f"⚠️ Notion 상태 업데이트 실패 (무시): {e}")

        # 성공 메시지
        commit_sha = result.get("commit_sha", "N/A")
        file_path = result.get("file_path", f"content/work-logs/daily/{date}.md")

        await client.chat_update(
          channel=REPORT_CHANNEL_ID,
          ts=message_ts,
          text=(
            f"✅ {user_mention}업무일지 발행 완료!\n\n"
            f"📅 날짜: {date}\n"
            f"📄 제목: {title}\n"
            f"🏷️ 태그: {', '.join(tags) if tags else '없음'}\n"
            f"🔗 커밋: {commit_sha}\n"
            f"📁 경로: {file_path}"
            f"{portfolio_status}"
          )
        )

        logger.info(f"✅ Published: {date} (commit: {commit_sha})")

      else:
        error_msg = result.get("error", "알 수 없는 오류")
        raise Exception(error_msg)

    except ValueError as ve:
      # 검증 오류
      await client.chat_update(
        channel=REPORT_CHANNEL_ID,
        ts=message_ts,
        text=(
          f"⚠️ {user_mention}업무일지 발행 실패\n\n"
          f"📅 날짜: {date or '알 수 없음'}\n\n"
          f"❌ 검증 오류: {str(ve)}"
        )
      )
      logger.warning(f"⚠️ Validation error: {ve}")

    except Exception as e:
      # 일반 오류
      await client.chat_update(
        channel=REPORT_CHANNEL_ID,
        ts=message_ts,
        text=(
          f"❌ {user_mention}업무일지 발행 중 오류 발생\n\n"
          f"📅 날짜: {date or '알 수 없음'}\n\n"
          f"오류: {str(e)}"
        )
      )
      logger.error(f"❌ Publish failed: {e}", exc_info=True)

  except Exception as e:
    logger.error(f"❌ Error in publish webhook handler: {e}", exc_info=True)


def register_publish_handler(app: AsyncApp):
  """발행 웹훅 핸들러 등록

  Note: 실제 메시지 처리는 chat_handlers.py에서 수행됩니다.
  이 함수는 호환성을 위해 유지됩니다.

  Args:
    app: Slack AsyncApp 인스턴스
  """
  logger.info("✅ Publish webhook handler registered (via chat_handlers)")
