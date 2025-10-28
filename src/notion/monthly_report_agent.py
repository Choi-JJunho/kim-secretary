"""월간 리포트 생성 및 관리"""

import logging
from calendar import monthrange
from typing import Callable, Dict, List, Optional

from .client import NotionClient
from .db_initializer import ensure_db_schema
from .db_schema import get_monthly_report_schema
from ..analyzers.monthly_analyzer import MonthlyAnalyzer
from ..common.notion_blocks import build_ai_feedback_blocks, append_blocks_batched
from ..common.types import ReportProcessResult

logger = logging.getLogger(__name__)


class MonthlyReportManager:
  """월간 리포트 생성 및 관리"""

  def __init__(
      self,
      notion_client: Optional[NotionClient] = None,
      ai_provider_type: str = "claude"
  ):
    """
    Initialize MonthlyReportManager

    Args:
        notion_client: NotionClient instance (creates new if None)
        ai_provider_type: AI provider type (gemini, claude, ollama)
    """
    self.client = notion_client or NotionClient()
    self.ai_provider_type = ai_provider_type
    self.analyzer = MonthlyAnalyzer(ai_provider_type=ai_provider_type)
    self.last_used_ai_provider: Optional[str] = None

    logger.info(f"✅ MonthlyReportManager initialized (AI: {ai_provider_type})")

  async def generate_monthly_report(
      self,
      year: int,
      month: int,
      weekly_report_database_id: str,
      monthly_report_database_id: str,
      progress_callback: Optional[Callable[[str], any]] = None,
      resume_page_id: Optional[str] = None
  ) -> ReportProcessResult:
    """
    월간 리포트 생성

    Args:
        year: 연도
        month: 월 (1-12)
        weekly_report_database_id: 주간 리포트 DB ID
        monthly_report_database_id: 월간 리포트 DB ID
        progress_callback: 진행 상태 콜백 함수
        resume_page_id: 이력서 페이지 ID (선택)

    Returns:
        생성 결과
    """
    logger.info(f"🔄 월간 리포트 생성 시작: {year}-{month:02d}")

    # 진행 상태 업데이트 헬퍼
    async def update_progress(status: str):
      if progress_callback:
        try:
          await progress_callback(status)
        except Exception as e:
          logger.warning(f"⚠️ Progress callback failed: {e}")

    try:
      # 1. DB 스키마 확인 및 초기화
      await update_progress("🔧 월간 리포트 DB 스키마 확인 중...")
      schema = get_monthly_report_schema()
      schema_ok = await ensure_db_schema(
          monthly_report_database_id,
          schema,
          title_property_name="월",  # Title 속성 이름
          notion_client=self.client
      )
      if not schema_ok:
        raise ValueError("월간 리포트 DB 스키마 초기화 실패")

      # 2. 월간 날짜 범위 계산
      await update_progress("📅 월간 날짜 범위 계산 중...")
      last_day = monthrange(year, month)[1]
      start_date = f"{year}-{month:02d}-01"
      end_date = f"{year}-{month:02d}-{last_day}"
      logger.info(f"📅 날짜 범위: {start_date} ~ {end_date}")

      # 3. 주간 리포트 조회
      await update_progress(f"📋 주간 리포트 조회 중... ({start_date} ~ {end_date})")
      weekly_reports = await self.client.query_weekly_reports_by_month(
          database_id=weekly_report_database_id,
          year=year,
          month=month
      )

      if not weekly_reports:
        raise ValueError(
            f"해당 월에 주간 리포트가 없습니다: {year}-{month:02d} ({start_date} ~ {end_date})")

      logger.info(f"📊 {len(weekly_reports)}개 주간 리포트 발견")

      # 4. AI 분석
      await update_progress(f"🤖 AI 분석 중... ({len(weekly_reports)}개 주간 리포트)")
      analysis = await self.analyzer.analyze_monthly_reports(weekly_reports, self.client, resume_page_id)
      self.last_used_ai_provider = self.analyzer.last_used_ai_provider

      # 폴백 발생 시 알림
      if self.last_used_ai_provider and \
         self.last_used_ai_provider.lower() != (self.ai_provider_type or "").lower():
        await update_progress(
            f"⚠️ AI 제공자 변경: {self.ai_provider_type} → {self.last_used_ai_provider}")
        logger.info(
            f"🔁 AI provider fallback: {self.ai_provider_type} -> {self.last_used_ai_provider}")

      # 5. 월간 리포트 페이지 생성
      await update_progress("📝 월간 리포트 페이지 생성 중...")

      # DB 스키마에서 실제 존재하는 속성 확인
      db_info = await self.client.get_database(monthly_report_database_id)
      existing_props = db_info.get('properties', {})

      # Title 속성 찾기
      title_prop_name = None
      for prop_name, prop_data in existing_props.items():
        if prop_data.get('type') == 'title':
          title_prop_name = prop_name
          logger.info(f"📌 Title 속성 발견: '{prop_name}'")
          break

      # Fallback: 속성을 찾을 수 없으면 Notion 기본값 사용
      if not title_prop_name:
        title_prop_name = "이름"  # Notion 한국어 기본 title 속성
        logger.info(f"⚠️ Title 속성을 찾을 수 없어 기본값 사용: '{title_prop_name}' (뷰일 가능성)")

      # Properties 구성 (존재하는 속성만 사용)
      properties = {
        title_prop_name: {
          "title": [
            {
              "text": {
                "content": f"{year}-{month:02d}"
              }
            }
          ]
        }
      }

      # 선택적 속성 추가 (존재하는 경우에만)
      if "시작일" in existing_props:
        properties["시작일"] = {"date": {"start": start_date}}
      if "종료일" in existing_props:
        properties["종료일"] = {"date": {"start": end_date}}

      logger.info(f"📊 사용 가능한 속성: {list(properties.keys())}")

      # 페이지 생성
      monthly_report_page = await self.client.create_page(
          database_id=monthly_report_database_id,
          properties=properties
      )

      page_id = monthly_report_page["id"]
      page_url = monthly_report_page.get("url", "")
      logger.info(f"✅ 월간 리포트 페이지 생성: {page_id}")

      # 6. 콘텐츠 추가 (마크다운 그대로 사용)
      await update_progress("✍️ 리포트 콘텐츠 작성 중...")
      blocks = build_ai_feedback_blocks(analysis)
      await append_blocks_batched(self.client.client, page_id, blocks)
      logger.info(f"✅ 리포트 콘텐츠 추가 완료: {page_id}")

      # 7. 주간 리포트와 Relation 연결 (선택사항)
      await update_progress("🔗 주간 리포트와 연결 중...")
      try:
        weekly_report_ids = [report["id"] for report in weekly_reports]
        await self.client.create_relation(
            page_id=page_id,
            property_name="주간리포트",
            target_page_ids=weekly_report_ids
        )
        logger.info("✅ 주간 리포트 Relation 연결 완료")
      except Exception as e:
        logger.warning(f"⚠️ 주간 리포트 Relation 연결 실패 (선택사항): {e}")
        # Relation 연결 실패는 치명적이지 않으므로 계속 진행

      logger.info(f"✅ 월간 리포트 생성 완료: {year}-{month:02d}")

      return {
        "success": True,
        "report_type": "monthly",
        "year": year,
        "period": month,
        "page_id": page_id,
        "page_url": page_url,
        "used_ai_provider": self.last_used_ai_provider or self.ai_provider_type,
        "weekly_reports_count": len(weekly_reports),
        "analysis": analysis
      }

    except Exception as e:
      logger.error(f"❌ 월간 리포트 생성 실패: {e}")
      raise

# Singleton instance
_monthly_report_manager = None


def get_monthly_report_manager(
    ai_provider_type: str = "claude"
) -> MonthlyReportManager:
  """
  Get or create singleton MonthlyReportManager instance

  Args:
      ai_provider_type: AI provider type (gemini, claude, ollama)

  Returns:
      MonthlyReportManager instance
  """
  global _monthly_report_manager
  if _monthly_report_manager is None or _monthly_report_manager.ai_provider_type != ai_provider_type:
    _monthly_report_manager = MonthlyReportManager(
        ai_provider_type=ai_provider_type)
  return _monthly_report_manager
