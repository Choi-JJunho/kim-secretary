"""
월간 리포트 배치 생성 스크립트

주간 리포트를 분석하여 누락된 월간 리포트를 자동으로 생성합니다.
3개씩 비동기로 동시 처리합니다.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytz
from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).parent.parent
env_file = project_root / '.env'
if env_file.exists():
  load_dotenv(env_file)
  print(f"✅ Loaded environment from {env_file}")
else:
  print(f"⚠️ No .env file found at {env_file}")

# Add project root to path
sys.path.insert(0, str(project_root))

from src.common.notion_utils import get_user_database_mapping
from src.notion.client import NotionClient
from src.notion.monthly_report_agent import get_monthly_report_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

KST = pytz.timezone('Asia/Seoul')

# Configuration
BATCH_SIZE = 3  # 동시 처리 개수 (월간 리포트는 더 무거우므로 3개)
AI_PROVIDER = "claude"  # 사용할 AI 제공자


class MonthlyReportBatchGenerator:
  """월간 리포트 배치 생성기"""

  def __init__(
      self,
      user_id: str,
      ai_provider: str = "claude",
      batch_size: int = 3
  ):
    """
    Initialize batch generator

    Args:
        user_id: Slack user ID
        ai_provider: AI provider type
        batch_size: 동시 처리할 월간 리포트 개수
    """
    self.user_id = user_id
    self.ai_provider = ai_provider
    self.batch_size = batch_size
    self.notion_client = NotionClient()
    self.monthly_manager = get_monthly_report_manager(ai_provider)

    # Get user database mappings
    user_dbs = get_user_database_mapping(user_id)
    if not user_dbs:
      raise ValueError(f"No database mapping found for user: {user_id}")

    self.weekly_report_db_id = user_dbs.get("weekly_report_db")
    self.monthly_report_db_id = user_dbs.get("monthly_report_db")

    if not self.weekly_report_db_id or not self.monthly_report_db_id:
      raise ValueError(f"Incomplete database mapping for user: {user_id}")

    logger.info(
        f"✅ Initialized for user {user_id} (AI: {ai_provider}, "
        f"batch_size: {batch_size})"
    )

  async def get_weekly_report_dates(self) -> List[str]:
    """
    주간 리포트 DB에서 모든 시작일을 가져옵니다.

    Returns:
        날짜 문자열 리스트 (YYYY-MM-DD)
    """
    logger.info("📅 주간 리포트 날짜 조회 중...")

    try:
      results = await self.notion_client.query_database(
          database_id=self.weekly_report_db_id,
          filter_params=None
      )

      dates = []
      for page in results:
        properties = page.get("properties", {})
        date_prop = properties.get("시작일", {}).get("date", {})

        if date_prop:
          date_str = date_prop.get("start")
          if date_str:
            dates.append(date_str)

      # Sort dates in Python
      dates.sort()

      logger.info(f"✅ 총 {len(dates)}개의 주간 리포트 발견")
      return dates

    except Exception as e:
      logger.error(f"❌ 주간 리포트 날짜 조회 실패: {e}")
      raise

  async def get_existing_monthly_reports(self) -> Set[str]:
    """
    이미 생성된 월간 리포트의 년-월 정보를 가져옵니다.

    Returns:
        년-월 문자열 집합 (예: {"2025-01", "2025-02"})
    """
    logger.info("📊 기존 월간 리포트 조회 중...")

    try:
      results = await self.notion_client.query_database(
          database_id=self.monthly_report_db_id,
          filter_params=None
      )

      existing_months = set()
      for page in results:
        properties = page.get("properties", {})

        # 년월 속성에서 추출
        month_prop = properties.get("년월", {})
        title_parts = month_prop.get("title", [])

        if title_parts:
          month_str = title_parts[0].get("plain_text", "")
          if month_str and len(month_str) == 7:  # YYYY-MM 형식
            existing_months.add(month_str)

      logger.info(f"✅ 기존 월간 리포트: {len(existing_months)}개")
      return existing_months

    except Exception as e:
      logger.error(f"❌ 월간 리포트 조회 실패: {e}")
      raise

  def group_dates_by_month(self, dates: List[str]) -> Dict[str, List[str]]:
    """
    날짜를 년-월로 그룹화합니다.

    Args:
        dates: 날짜 문자열 리스트

    Returns:
        년-월별 날짜 딕셔너리
    """
    months = {}

    for date_str in dates:
      try:
        date = datetime.fromisoformat(date_str)
        month_key = f"{date.year}-{date.month:02d}"

        if month_key not in months:
          months[month_key] = []
        months[month_key].append(date_str)

      except (ValueError, IndexError):
        logger.warning(f"⚠️ Invalid date format: {date_str}")
        continue

    return months

  async def generate_monthly_report(
      self,
      year: int,
      month: int,
      semaphore: asyncio.Semaphore
  ) -> Tuple[str, bool, str]:
    """
    월간 리포트를 생성합니다 (동시 실행 제한 적용).

    Args:
        year: 연도
        month: 월
        semaphore: 동시 실행 제한용 Semaphore

    Returns:
        (month_str, success, message) 튜플
    """
    month_str = f"{year}-{month:02d}"

    async with semaphore:
      logger.info(f"🔄 [{month_str}] 월간 리포트 생성 시작...")

      try:
        result = await self.monthly_manager.generate_monthly_report(
            year=year,
            month=month,
            weekly_report_database_id=self.weekly_report_db_id,
            monthly_report_database_id=self.monthly_report_db_id,
            progress_callback=None  # 배치 모드에서는 progress 콜백 없음
        )

        page_url = result.get('page_url', '')
        weekly_reports_count = result.get('weekly_reports_count', 0)

        logger.info(
            f"✅ [{month_str}] 완료! (주간 리포트: {weekly_reports_count}개)"
        )

        return month_str, True, page_url

      except ValueError as e:
        # 주간 리포트가 없는 경우 등
        logger.warning(f"⚠️ [{month_str}] 건너뜀: {e}")
        return month_str, False, str(e)

      except Exception as e:
        logger.error(f"❌ [{month_str}] 실패: {e}")
        return month_str, False, str(e)

  async def generate_missing_reports(
      self,
      missing_months: List[Tuple[int, int]]
  ) -> Dict[str, any]:
    """
    누락된 월간 리포트를 배치로 생성합니다.

    Args:
        missing_months: (year, month) 튜플 리스트

    Returns:
        생성 결과 딕셔너리
    """
    if not missing_months:
      logger.info("✅ 생성할 월간 리포트가 없습니다.")
      return {
        "total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "results": []
      }

    logger.info(f"\n{'='*60}")
    logger.info(f"📦 배치 생성 시작: {len(missing_months)}개 월")
    logger.info(f"⚙️ 동시 처리: {self.batch_size}개")
    logger.info(f"🤖 AI: {self.ai_provider}")
    logger.info(f"{'='*60}\n")

    # Semaphore for limiting concurrent tasks
    semaphore = asyncio.Semaphore(self.batch_size)

    # Create tasks
    tasks = []
    for year, month in missing_months:
      task = self.generate_monthly_report(year, month, semaphore)
      tasks.append(task)

    # Execute all tasks
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Analyze results
    success_count = 0
    failed_count = 0
    skipped_count = 0
    details = []

    for result in results:
      if isinstance(result, Exception):
        failed_count += 1
        details.append({
          "month": "unknown",
          "success": False,
          "message": str(result)
        })
      else:
        month_str, success, message = result
        if success:
          success_count += 1
        elif "건너뜀" in message or "없음" in message:
          skipped_count += 1
        else:
          failed_count += 1

        details.append({
          "month": month_str,
          "success": success,
          "message": message
        })

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ 배치 생성 완료!")
    logger.info(f"{'='*60}")
    logger.info(f"📊 총 시도: {len(missing_months)}개")
    logger.info(f"✅ 성공: {success_count}개")
    logger.info(f"⚠️ 건너뜀: {skipped_count}개")
    logger.info(f"❌ 실패: {failed_count}개")
    logger.info(f"{'='*60}\n")

    return {
      "total": len(missing_months),
      "success": success_count,
      "failed": failed_count,
      "skipped": skipped_count,
      "results": details
    }

  async def run(self) -> Dict[str, any]:
    """
    배치 생성 프로세스를 실행합니다.

    Returns:
        실행 결과 딕셔너리
    """
    try:
      # 1. Get all weekly report dates
      weekly_report_dates = await self.get_weekly_report_dates()

      if not weekly_report_dates:
        logger.info("⚠️ 주간 리포트가 없습니다.")
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

      # 2. Group by month
      months_with_reports = self.group_dates_by_month(weekly_report_dates)
      logger.info(f"📅 주간 리포트가 있는 월: {len(months_with_reports)}개")

      # 3. Get existing monthly reports
      existing_reports = await self.get_existing_monthly_reports()

      # 4. Find missing months
      missing_month_strs = set(months_with_reports.keys()) - existing_reports
      missing_months = []

      for month_str in sorted(missing_month_strs):
        try:
          year, month = map(int, month_str.split('-'))
          missing_months.append((year, month))
        except (ValueError, IndexError):
          continue

      logger.info(f"🔍 생성할 월간 리포트: {len(missing_months)}개")

      if missing_months:
        # Show missing months
        logger.info("\n📋 생성 대상 월:")
        for year, month in sorted(missing_months):
          month_str = f"{year}-{month:02d}"
          reports_count = len(months_with_reports.get(month_str, []))
          logger.info(f"  • {month_str} (주간 리포트 {reports_count}개)")

      # 5. Generate missing reports
      result = await self.generate_missing_reports(missing_months)

      return result

    except Exception as e:
      logger.error(f"❌ 배치 생성 실패: {e}", exc_info=True)
      raise


async def main():
  """메인 함수"""
  import argparse

  parser = argparse.ArgumentParser(
      description="월간 리포트 배치 생성"
  )
  parser.add_argument(
      "--user-id",
      type=str,
      help="Slack User ID (환경변수 NOTION_USER_DATABASE_MAPPING에서 자동 탐지 가능)"
  )
  parser.add_argument(
      "--ai-provider",
      type=str,
      default="claude",
      choices=["gemini", "claude", "ollama"],
      help="AI 제공자 (기본값: claude)"
  )
  parser.add_argument(
      "--batch-size",
      type=int,
      default=3,
      help="동시 처리 개수 (기본값: 3)"
  )
  parser.add_argument(
      "--all-users",
      action="store_true",
      help="모든 유저에 대해 배치 생성"
  )

  args = parser.parse_args()

  # Get user IDs
  user_ids = []

  if args.all_users:
    # Get all user IDs from environment
    user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")
    try:
      user_db_mapping = json.loads(user_db_mapping_str)
      user_ids = list(user_db_mapping.keys())
      logger.info(f"✅ {len(user_ids)}명의 유저 발견")
    except json.JSONDecodeError:
      logger.error("❌ NOTION_USER_DATABASE_MAPPING 파싱 실패")
      sys.exit(1)

  elif args.user_id:
    user_ids = [args.user_id]

  else:
    # Try to get first user from environment
    user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")
    try:
      user_db_mapping = json.loads(user_db_mapping_str)
      if user_db_mapping:
        user_ids = [list(user_db_mapping.keys())[0]]
        logger.info(f"✅ 첫 번째 유저 사용: {user_ids[0]}")
      else:
        logger.error("❌ 유저를 찾을 수 없습니다. --user-id 또는 --all-users 옵션을 사용하세요.")
        sys.exit(1)
    except json.JSONDecodeError:
      logger.error("❌ NOTION_USER_DATABASE_MAPPING 파싱 실패")
      sys.exit(1)

  # Process each user
  for user_id in user_ids:
    logger.info(f"\n{'='*60}")
    logger.info(f"👤 유저: {user_id}")
    logger.info(f"{'='*60}\n")

    try:
      generator = MonthlyReportBatchGenerator(
          user_id=user_id,
          ai_provider=args.ai_provider,
          batch_size=args.batch_size
      )

      result = await generator.run()

      # Print summary
      logger.info(f"\n{'='*60}")
      logger.info(f"📊 최종 결과 (유저: {user_id})")
      logger.info(f"{'='*60}")
      logger.info(f"총 시도: {result['total']}개")
      logger.info(f"✅ 성공: {result['success']}개")
      logger.info(f"⚠️ 건너뜀: {result['skipped']}개")
      logger.info(f"❌ 실패: {result['failed']}개")
      logger.info(f"{'='*60}\n")

    except Exception as e:
      logger.error(f"❌ 유저 {user_id} 처리 실패: {e}")
      continue

  logger.info("✅ 모든 처리 완료!")


if __name__ == "__main__":
  asyncio.run(main())
