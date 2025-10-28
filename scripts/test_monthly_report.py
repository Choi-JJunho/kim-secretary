"""월간 리포트 생성 테스트 스크립트"""

import asyncio
import logging
import os
import sys
from datetime import datetime

import pytz
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.notion.monthly_report_agent import get_monthly_report_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


async def test_monthly_report():
  """월간 리포트 생성 테스트"""
  try:
    load_dotenv()

    # Get current month
    now = datetime.now(KST)
    current_year = now.year
    current_month = now.month

    logger.info(f"📅 현재: {current_year}-{current_month:02d}")

    # Get DB IDs from environment (unified mapping)
    import json
    user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")

    if not user_db_mapping_str or user_db_mapping_str == "{}":
      logger.error("❌ NOTION_USER_DATABASE_MAPPING 환경 변수가 설정되지 않았습니다!")
      logger.info("환경 변수 형식:")
      logger.info('{"USER_ID":{"alias":"홍길동","weekly_report_db":"DB_ID","monthly_report_db":"DB_ID"}}')
      return

    try:
      user_db_mapping = json.loads(user_db_mapping_str)
    except json.JSONDecodeError as e:
      logger.error(f"❌ JSON 파싱 실패: {e}")
      return

    # Get first user's DB IDs
    if not user_db_mapping:
      logger.error("❌ 데이터베이스 매핑이 비어있습니다!")
      return

    user_id = list(user_db_mapping.keys())[0]
    user_dbs = user_db_mapping[user_id]

    user_alias = user_dbs.get("alias", "이름없음")
    weekly_report_db_id = user_dbs.get("weekly_report_db")
    monthly_report_db_id = user_dbs.get("monthly_report_db")
    resume_page_id = user_dbs.get("resume_page")  # 선택사항

    if not weekly_report_db_id or not monthly_report_db_id:
      logger.error("❌ 데이터베이스 ID가 불완전합니다!")
      logger.error(f"weekly_report_db: {weekly_report_db_id}")
      logger.error(f"monthly_report_db: {monthly_report_db_id}")
      return

    logger.info(f"✅ DB 설정 확인 완료")
    logger.info(f"  User: {user_alias} ({user_id})")
    logger.info(f"  Weekly Report DB: {weekly_report_db_id}")
    logger.info(f"  Monthly Report DB: {monthly_report_db_id}")
    if resume_page_id:
      logger.info(f"  Resume Page: {resume_page_id}")

    # Ask for year and month (with non-interactive mode support)
    print("\n" + "=" * 80)
    print("월간 리포트 생성 테스트")
    print("=" * 80)

    # Check if running interactively
    is_interactive = sys.stdin.isatty()

    if is_interactive:
      year_input = input(f"연도 입력 (기본값: {current_year}): ").strip()
      year = int(year_input) if year_input else current_year

      month_input = input(f"월 입력 (기본값: {current_month}): ").strip()
      month = int(month_input) if month_input else current_month

      ai_provider_input = input(
          "AI 모델 선택 (gemini/claude/ollama, 기본값: claude): ").strip().lower()
      ai_provider = ai_provider_input if ai_provider_input in [
          "gemini", "claude", "ollama"] else "claude"
    else:
      # Non-interactive mode: use defaults or command-line args
      year = int(sys.argv[1]) if len(sys.argv) > 1 else current_year
      month = int(sys.argv[2]) if len(sys.argv) > 2 else current_month
      ai_provider = sys.argv[3] if len(sys.argv) > 3 else "claude"

      logger.info(f"🤖 Non-interactive mode detected")
      logger.info(f"  연도: {year} (기본값 사용)" if len(sys.argv) <= 1 else f"  연도: {year}")
      logger.info(f"  월: {month} (기본값 사용)" if len(sys.argv) <= 2 else f"  월: {month}")
      logger.info(f"  AI: {ai_provider} (기본값 사용)" if len(sys.argv) <= 3 else f"  AI: {ai_provider}")

    print("\n" + "=" * 80)
    logger.info(f"🚀 월간 리포트 생성 시작")
    logger.info(f"  기간: {year}-{month:02d}")
    logger.info(f"  AI: {ai_provider.upper()}")
    print("=" * 80 + "\n")

    # Progress callback
    async def progress_callback(status: str):
      logger.info(f"⏳ {status}")

    # Get manager and generate report
    manager = get_monthly_report_manager(ai_provider_type=ai_provider)

    result = await manager.generate_monthly_report(
        year=year,
        month=month,
        weekly_report_database_id=weekly_report_db_id,
        monthly_report_database_id=monthly_report_db_id,
        progress_callback=progress_callback,
        resume_page_id=resume_page_id
    )

    # Print results
    print("\n" + "=" * 80)
    print("✅ 월간 리포트 생성 완료!")
    print("=" * 80)
    print(f"\n📆 기간: {year}-{month:02d}")
    print(f"🤖 AI: {result.get('used_ai_provider', ai_provider).upper()}")
    print(f"📊 분석한 주간 리포트: {result.get('weekly_reports_count', 0)}개")
    print(f"📄 페이지 ID: {result.get('page_id', 'N/A')}")

    if result.get('page_url'):
      print(f"🔗 URL: {result['page_url']}")

    # Print analysis summary (markdown text)
    analysis = result.get('analysis', '')
    if analysis and isinstance(analysis, str):
      print("\n" + "-" * 80)
      print("📋 분석 미리보기")
      print("-" * 80)
      # 마크다운 텍스트의 앞부분만 출력
      preview_length = 500
      if len(analysis) > preview_length:
        print(f"\n{analysis[:preview_length]}...\n\n(총 {len(analysis)}자)")
      else:
        print(f"\n{analysis}")

    print("\n" + "=" * 80)
    print("✨ Notion에서 확인하세요!")
    print("=" * 80 + "\n")

  except ValueError as e:
    logger.error(f"⚠️ 검증 오류: {e}")
  except Exception as e:
    logger.error(f"❌ 테스트 실패: {e}", exc_info=True)


if __name__ == "__main__":
  asyncio.run(test_monthly_report())
