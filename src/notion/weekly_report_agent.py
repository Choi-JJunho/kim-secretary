"""주간 리포트 생성 및 관리"""

import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

import pytz

from .client import NotionClient
from .db_initializer import ensure_db_schema
from .db_schema import get_weekly_report_schema
from ..analyzers import WeeklyAnalyzer
from ..common.notion_blocks import build_ai_feedback_blocks, append_blocks_batched
from ..common.types import ReportProcessResult

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


def get_week_range(year: int, week: int) -> tuple[str, str]:
  """
  ISO week number로 주간 날짜 범위 계산 (월요일~일요일)

  Args:
      year: 연도
      week: ISO week number (1-53)

  Returns:
      (start_date, end_date) tuple in YYYY-MM-DD format
  """
  # ISO week date: year-W{week}-1 (Monday)
  jan_4 = datetime(year, 1, 4, tzinfo=KST)
  week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
  target_monday = week_1_monday + timedelta(weeks=week - 1)
  target_sunday = target_monday + timedelta(days=6)

  start_date = target_monday.strftime("%Y-%m-%d")
  end_date = target_sunday.strftime("%Y-%m-%d")

  return start_date, end_date


class WeeklyReportManager:
  """주간 리포트 생성 및 관리"""

  def __init__(
      self,
      notion_client: Optional[NotionClient] = None,
      ai_provider_type: str = "claude"
  ):
    """
    Initialize WeeklyReportManager

    Args:
        notion_client: NotionClient instance (creates new if None)
        ai_provider_type: AI provider type (gemini, claude, ollama)
    """
    self.client = notion_client or NotionClient()
    self.ai_provider_type = ai_provider_type
    self.analyzer = WeeklyAnalyzer(ai_provider_type=ai_provider_type)
    self.last_used_ai_provider: Optional[str] = None

    logger.info(f"✅ WeeklyReportManager initialized (AI: {ai_provider_type})")

  async def generate_weekly_report(
      self,
      year: int,
      week: int,
      work_log_database_id: str,
      weekly_report_database_id: str,
      progress_callback: Optional[Callable[[str], any]] = None,
      resume_page_id: Optional[str] = None
  ) -> ReportProcessResult:
    """
    주간 리포트 생성

    Args:
        year: 연도
        week: ISO week number
        work_log_database_id: 업무일지 DB ID
        weekly_report_database_id: 주간 리포트 DB ID
        progress_callback: 진행 상태 콜백 함수
        resume_page_id: 이력서 페이지 ID (선택)

    Returns:
        생성 결과
    """
    logger.info(f"🔄 주간 리포트 생성 시작: {year}-W{week:02d}")

    # 진행 상태 업데이트 헬퍼
    async def update_progress(status: str):
      if progress_callback:
        try:
          await progress_callback(status)
        except Exception as e:
          logger.warning(f"⚠️ Progress callback failed: {e}")

    try:
      # 1. DB 스키마 확인 및 초기화
      await update_progress("🔧 주간 리포트 DB 스키마 확인 중...")
      schema = get_weekly_report_schema()
      schema_ok = await ensure_db_schema(
          weekly_report_database_id,
          schema,
          title_property_name="주차",  # Title 속성 이름
          notion_client=self.client
      )
      if not schema_ok:
        raise ValueError("주간 리포트 DB 스키마 초기화 실패")

      # 2. 주간 날짜 범위 계산
      await update_progress("📅 주간 날짜 범위 계산 중...")
      start_date, end_date = get_week_range(year, week)
      logger.info(f"📅 날짜 범위: {start_date} ~ {end_date}")

      # 3. 업무일지 조회
      await update_progress(f"📋 업무일지 조회 중... ({start_date} ~ {end_date})")
      daily_logs = await self.client.query_work_logs_by_date_range(
          database_id=work_log_database_id,
          start_date=start_date,
          end_date=end_date
      )

      if not daily_logs:
        raise ValueError(
            f"해당 주간에 업무일지가 없습니다: {year}-W{week:02d} ({start_date} ~ {end_date})")

      logger.info(f"📊 {len(daily_logs)}개 업무일지 발견")

      # 4. AI 분석
      await update_progress(f"🤖 AI 분석 중... ({len(daily_logs)}개 업무일지)")
      analysis = await self.analyzer.analyze_weekly_logs(daily_logs, self.client, resume_page_id)
      self.last_used_ai_provider = self.analyzer.last_used_ai_provider

      # 폴백 발생 시 알림
      if self.last_used_ai_provider and \
         self.last_used_ai_provider.lower() != (self.ai_provider_type or "").lower():
        await update_progress(
            f"⚠️ AI 제공자 변경: {self.ai_provider_type} → {self.last_used_ai_provider}")
        logger.info(
            f"🔁 AI provider fallback: {self.ai_provider_type} -> {self.last_used_ai_provider}")

      # 5. 주간 리포트 페이지 생성
      await update_progress("📝 주간 리포트 페이지 생성 중...")

      # DB 스키마에서 실제 존재하는 속성 확인
      db_info = await self.client.get_database(weekly_report_database_id)
      existing_props = db_info.get('properties', {})

      # Title 속성 찾기
      title_prop_name = None
      for prop_name, prop_data in existing_props.items():
        if prop_data.get('type') == 'title':
          title_prop_name = prop_name
          logger.info(f"📌 Title 속성 발견: '{prop_name}'")
          break

      # Fallback: 속성을 찾을 수 없으면 기본값 사용
      if not title_prop_name:
        title_prop_name = "주차"  # 주간 리포트 기본 title 속성
        logger.info(f"⚠️ Title 속성을 찾을 수 없어 기본값 사용: '{title_prop_name}'")

      # Properties 구성 (title만 사용)
      properties = {
        title_prop_name: {
          "title": [
            {
              "text": {
                "content": f"{year}-W{week:02d}"
              }
            }
          ]
        }
      }

      logger.info(f"📊 사용 가능한 속성: {list(properties.keys())}")

      # 페이지 생성
      weekly_report_page = await self.client.create_page(
          database_id=weekly_report_database_id,
          properties=properties
      )

      page_id = weekly_report_page["id"]
      page_url = weekly_report_page.get("url", "")
      logger.info(f"✅ 주간 리포트 페이지 생성: {page_id}")

      # 6. 콘텐츠 추가 (마크다운 그대로 사용)
      await update_progress("✍️ 리포트 콘텐츠 작성 중...")
      blocks = build_ai_feedback_blocks(analysis)
      await append_blocks_batched(self.client.client, page_id, blocks)
      logger.info(f"✅ 리포트 콘텐츠 추가 완료: {page_id}")

      # 7. 업무일지와 Relation 연결 (선택사항)
      await update_progress("🔗 업무일지와 연결 중...")
      try:
        daily_log_ids = [log["id"] for log in daily_logs]
        await self.client.create_relation(
            page_id=page_id,
            property_name="일지목록",
            target_page_ids=daily_log_ids
        )
        logger.info("✅ 업무일지 Relation 연결 완료")
      except Exception as e:
        logger.warning(f"⚠️ 업무일지 Relation 연결 실패 (선택사항): {e}")
        # Relation 연결 실패는 치명적이지 않으므로 계속 진행

      logger.info(f"✅ 주간 리포트 생성 완료: {year}-W{week:02d}")

      return {
        "success": True,
        "report_type": "weekly",
        "year": year,
        "period": week,
        "page_id": page_id,
        "page_url": page_url,
        "used_ai_provider": self.last_used_ai_provider or self.ai_provider_type,
        "daily_logs_count": len(daily_logs),
        "analysis": analysis  # 마크다운 텍스트
      }

    except Exception as e:
      logger.error(f"❌ 주간 리포트 생성 실패: {e}")
      raise


# Singleton instance
_weekly_report_manager = None


def get_weekly_report_manager(
    ai_provider_type: str = "claude"
) -> WeeklyReportManager:
  """
  Get or create singleton WeeklyReportManager instance

  Args:
      ai_provider_type: AI provider type (gemini, claude, ollama)

  Returns:
      WeeklyReportManager instance
  """
  global _weekly_report_manager
  if _weekly_report_manager is None or _weekly_report_manager.ai_provider_type != ai_provider_type:
    _weekly_report_manager = WeeklyReportManager(
        ai_provider_type=ai_provider_type)
  return _weekly_report_manager
