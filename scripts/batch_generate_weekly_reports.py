"""
주간 리포트 배치 생성 스크립트

업무일지를 분석하여 누락된 주간 리포트를 자동으로 생성합니다.
5개씩 비동기로 동시 처리합니다.
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

from src.common.date_utils import get_week_info, format_week_string
from src.common.notion_utils import get_user_database_mapping
from src.notion.client import NotionClient
from src.notion.weekly_report_agent import get_weekly_report_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

KST = pytz.timezone('Asia/Seoul')

# Configuration
BATCH_SIZE = 5  # 동시 처리 개수
AI_PROVIDER = "claude"  # 사용할 AI 제공자


class WeeklyReportBatchGenerator:
  """주간 리포트 배치 생성기"""

  def __init__(
      self,
      user_id: str,
      ai_provider: str = "claude",
      batch_size: int = 5
  ):
    """
    Initialize batch generator

    Args:
        user_id: Slack user ID
        ai_provider: AI provider type
        batch_size: 동시 처리할 주간 리포트 개수
    """
    self.user_id = user_id
    self.ai_provider = ai_provider
    self.batch_size = batch_size
    self.notion_client = NotionClient()
    self.weekly_manager = get_weekly_report_manager(ai_provider)

    # Get user database mappings
    user_dbs = get_user_database_mapping(user_id)
    if not user_dbs:
      raise ValueError(f"No database mapping found for user: {user_id}")

    self.work_log_db_id = user_dbs.get("work_log_db")
    self.weekly_report_db_id = user_dbs.get("weekly_report_db")

    if not self.work_log_db_id or not self.weekly_report_db_id:
      raise ValueError(f"Incomplete database mapping for user: {user_id}")

    logger.info(
        f"✅ Initialized for user {user_id} (AI: {ai_provider}, "
        f"batch_size: {batch_size})"
    )

  async def get_work_log_dates(self) -> List[str]:
    """
    업무일지 DB에서 모든 작성일을 가져옵니다.

    Returns:
        날짜 문자열 리스트 (YYYY-MM-DD)
    """
    logger.info("📅 업무일지 날짜 조회 중...")

    try:
      results = await self.notion_client.query_database(
          database_id=self.work_log_db_id,
          filter_params=None
      )

      dates = []
      for page in results:
        properties = page.get("properties", {})
        date_prop = properties.get("작성일", {}).get("date", {})

        if date_prop:
          date_str = date_prop.get("start")
          if date_str:
            dates.append(date_str)

      # Sort dates in Python
      dates.sort()

      logger.info(f"✅ 총 {len(dates)}개의 업무일지 발견")
      return dates

    except Exception as e:
      logger.error(f"❌ 업무일지 날짜 조회 실패: {e}")
      raise

  async def get_existing_weekly_reports(self) -> Set[str]:
    """
    이미 생성된 주간 리포트의 주차 정보를 가져옵니다.

    Returns:
        주차 문자열 집합 (예: {"2025-W03", "2025-W04"})
    """
    logger.info("📊 기존 주간 리포트 조회 중...")

    try:
      results = await self.notion_client.query_database(
          database_id=self.weekly_report_db_id,
          filter_params=None
      )

      existing_weeks = set()
      for page in results:
        properties = page.get("properties", {})

        # 주차 속성에서 추출
        week_prop = properties.get("주차", {})
        title_parts = week_prop.get("title", [])

        if title_parts:
          week_str = title_parts[0].get("plain_text", "")
          if week_str and "-W" in week_str:
            existing_weeks.add(week_str)

      logger.info(f"✅ 기존 주간 리포트: {len(existing_weeks)}개")
      return existing_weeks

    except Exception as e:
      logger.error(f"❌ 주간 리포트 조회 실패: {e}")
      raise

  def group_dates_by_week(self, dates: List[str]) -> Dict[str, List[str]]:
    """
    날짜를 주차별로 그룹화합니다.

    Args:
        dates: 날짜 문자열 리스트

    Returns:
        주차별 날짜 딕셔너리
    """
    weeks = {}

    for date_str in dates:
      try:
        date = datetime.fromisoformat(date_str)
        year, week = get_week_info(date)
        week_key = format_week_string(year, week)

        if week_key not in weeks:
          weeks[week_key] = []
        weeks[week_key].append(date_str)

      except (ValueError, IndexError):
        logger.warning(f"⚠️ Invalid date format: {date_str}")
        continue

    return weeks

  async def generate_weekly_report(
      self,
      year: int,
      week: int,
      semaphore: asyncio.Semaphore
  ) -> Tuple[str, bool, str]:
    """
    주간 리포트를 생성합니다 (동시 실행 제한 적용).

    Args:
        year: 연도
        week: 주차
        semaphore: 동시 실행 제한용 Semaphore

    Returns:
        (week_str, success, message) 튜플
    """
    week_str = format_week_string(year, week)

    async with semaphore:
      logger.info(f"🔄 [{week_str}] 주간 리포트 생성 시작...")

      try:
        result = await self.weekly_manager.generate_weekly_report(
            year=year,
            week=week,
            work_log_database_id=self.work_log_db_id,
            weekly_report_database_id=self.weekly_report_db_id,
            progress_callback=None  # 배치 모드에서는 progress 콜백 없음
        )

        page_url = result.get('page_url', '')
        daily_logs_count = result.get('daily_logs_count', 0)

        logger.info(
            f"✅ [{week_str}] 완료! (업무일지: {daily_logs_count}개)"
        )

        return week_str, True, page_url

      except ValueError as e:
        # 업무일지가 없는 경우 등
        logger.warning(f"⚠️ [{week_str}] 건너뜀: {e}")
        return week_str, False, str(e)

      except Exception as e:
        logger.error(f"❌ [{week_str}] 실패: {e}")
        return week_str, False, str(e)

  async def generate_missing_reports(
      self,
      missing_weeks: List[Tuple[int, int]]
  ) -> Dict[str, any]:
    """
    누락된 주간 리포트를 배치로 생성합니다.

    Args:
        missing_weeks: (year, week) 튜플 리스트

    Returns:
        생성 결과 딕셔너리
    """
    if not missing_weeks:
      logger.info("✅ 생성할 주간 리포트가 없습니다.")
      return {
        "total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "results": []
      }

    logger.info(f"\n{'='*60}")
    logger.info(f"📦 배치 생성 시작: {len(missing_weeks)}개 주차")
    logger.info(f"⚙️ 동시 처리: {self.batch_size}개")
    logger.info(f"🤖 AI: {self.ai_provider}")
    logger.info(f"{'='*60}\n")

    # Semaphore for limiting concurrent tasks
    semaphore = asyncio.Semaphore(self.batch_size)

    # Create tasks
    tasks = []
    for year, week in missing_weeks:
      task = self.generate_weekly_report(year, week, semaphore)
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
          "week": "unknown",
          "success": False,
          "message": str(result)
        })
      else:
        week_str, success, message = result
        if success:
          success_count += 1
        elif "건너뜀" in message or "없음" in message:
          skipped_count += 1
        else:
          failed_count += 1

        details.append({
          "week": week_str,
          "success": success,
          "message": message
        })

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ 배치 생성 완료!")
    logger.info(f"{'='*60}")
    logger.info(f"📊 총 시도: {len(missing_weeks)}개")
    logger.info(f"✅ 성공: {success_count}개")
    logger.info(f"⚠️ 건너뜀: {skipped_count}개")
    logger.info(f"❌ 실패: {failed_count}개")
    logger.info(f"{'='*60}\n")

    return {
      "total": len(missing_weeks),
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
      # 1. Get all work log dates
      work_log_dates = await self.get_work_log_dates()

      if not work_log_dates:
        logger.info("⚠️ 업무일지가 없습니다.")
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

      # 2. Group by week
      weeks_with_logs = self.group_dates_by_week(work_log_dates)
      logger.info(f"📅 업무일지가 있는 주차: {len(weeks_with_logs)}개")

      # 3. Get existing reports
      existing_reports = await self.get_existing_weekly_reports()

      # 4. Find missing weeks
      missing_week_strs = set(weeks_with_logs.keys()) - existing_reports
      missing_weeks = []

      for week_str in sorted(missing_week_strs):
        try:
          year, week = map(int, week_str.replace('W', '-').split('-')[0:3:2])
          missing_weeks.append((year, week))
        except (ValueError, IndexError):
          continue

      logger.info(f"🔍 생성할 주간 리포트: {len(missing_weeks)}개")

      if missing_weeks:
        # Show missing weeks
        logger.info("\n📋 생성 대상 주차:")
        for year, week in sorted(missing_weeks):
          week_str = format_week_string(year, week)
          dates_count = len(weeks_with_logs.get(week_str, []))
          logger.info(f"  • {week_str} (업무일지 {dates_count}개)")

      # 5. Generate missing reports
      result = await self.generate_missing_reports(missing_weeks)

      return result

    except Exception as e:
      logger.error(f"❌ 배치 생성 실패: {e}", exc_info=True)
      raise


async def main():
  """메인 함수"""
  import argparse

  parser = argparse.ArgumentParser(
      description="주간 리포트 배치 생성"
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
      default=5,
      help="동시 처리 개수 (기본값: 5)"
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
      generator = WeeklyReportBatchGenerator(
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
