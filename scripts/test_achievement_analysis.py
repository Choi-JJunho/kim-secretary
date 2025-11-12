"""성과 분석 테스트 스크립트"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta

import pytz
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.notion.achievement_agent import get_achievement_agent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


async def test_single_page():
  """단일 페이지 성과 분석 테스트"""
  try:
    load_dotenv()

    # Get page ID from user
    print("\n" + "=" * 80)
    print("단일 페이지 성과 분석 테스트")
    print("=" * 80)

    # Check if running interactively
    is_interactive = sys.stdin.isatty()

    if is_interactive:
      page_id = input("분석할 페이지 ID 입력: ").strip()
      if not page_id:
        logger.error("❌ 페이지 ID가 입력되지 않았습니다!")
        return

      ai_provider_input = input(
          "AI 모델 선택 (gemini/claude/ollama, 기본값: claude): ").strip().lower()
      ai_provider = ai_provider_input if ai_provider_input in [
          "gemini", "claude", "ollama"] else "claude"
    else:
      # Non-interactive mode: use command-line args
      if len(sys.argv) < 2:
        logger.error("❌ 페이지 ID를 인자로 전달해주세요!")
        logger.info("사용법: python test_achievement_analysis.py <page_id> [ai_provider]")
        return

      page_id = sys.argv[1]
      ai_provider = sys.argv[2] if len(sys.argv) > 2 else "claude"

      logger.info(f"🤖 Non-interactive mode detected")
      logger.info(f"  페이지 ID: {page_id}")
      logger.info(f"  AI: {ai_provider}")

    print("\n" + "=" * 80)
    logger.info(f"🚀 성과 분석 시작")
    logger.info(f"  페이지 ID: {page_id}")
    logger.info(f"  AI: {ai_provider.upper()}")
    print("=" * 80 + "\n")

    # Progress callback
    async def progress_callback(status: str):
      logger.info(f"⏳ {status}")

    # Get agent and analyze
    agent = get_achievement_agent(ai_provider_type=ai_provider)
    result = await agent.analyze_work_log(
        page_id=page_id,
        progress_callback=progress_callback
    )

    # Print results
    print("\n" + "=" * 80)
    if result.get("success"):
      print("✅ 성과 분석 완료!")
      print("=" * 80)
      print(f"\n📄 페이지 ID: {result.get('page_id', 'N/A')}")
      print(f"🤖 AI: {result.get('used_ai_provider', ai_provider).upper()}")
      print(f"🎯 추출된 성과: {result.get('achievements_count', 0)}개")

      # Print achievements
      achievements = result.get('achievements', [])
      if achievements:
        print("\n" + "-" * 80)
        print("📊 추출된 성과 목록")
        print("-" * 80)
        for i, achievement in enumerate(achievements, 1):
          print(f"\n{i}. {achievement.get('title', 'N/A')}")
          print(f"   카테고리: {achievement.get('category', 'N/A')}")
          print(f"   우선순위: {achievement.get('priority', 0)}/10")
          print(f"   기술 스택: {', '.join(achievement.get('tech_stack', []))}")

      # Print STAR format
      achievements_star = result.get('achievements_star', [])
      if achievements_star:
        print("\n" + "-" * 80)
        print("⭐ STAR 형식 변환")
        print("-" * 80)
        for i, star in enumerate(achievements_star, 1):
          print(f"\n{i}. {star}\n")

      print("\n" + "=" * 80)
      print("✨ Notion에서 확인하세요!")
      print("=" * 80 + "\n")
    else:
      print("❌ 성과 분석 실패!")
      print("=" * 80)
      print(f"\n메시지: {result.get('message', 'Unknown error')}")
      print()

  except Exception as e:
    logger.error(f"❌ 테스트 실패: {e}", exc_info=True)


async def test_batch_analysis():
  """배치 성과 분석 테스트"""
  try:
    load_dotenv()

    # Get DB IDs from environment
    user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")

    if not user_db_mapping_str or user_db_mapping_str == "{}":
      logger.error("❌ NOTION_USER_DATABASE_MAPPING 환경 변수가 설정되지 않았습니다!")
      return

    user_db_mapping = json.loads(user_db_mapping_str)
    if not user_db_mapping:
      logger.error("❌ 데이터베이스 매핑이 비어있습니다!")
      return

    user_id = list(user_db_mapping.keys())[0]
    user_dbs = user_db_mapping[user_id]

    user_alias = user_dbs.get("alias", "이름없음")
    work_log_db_id = user_dbs.get("work_log_db")

    if not work_log_db_id:
      logger.error("❌ work_log_db ID가 설정되지 않았습니다!")
      return

    logger.info(f"✅ DB 설정 확인 완료")
    logger.info(f"  User: {user_alias} ({user_id})")
    logger.info(f"  Work Log DB: {work_log_db_id}")

    # Get date range
    print("\n" + "=" * 80)
    print("배치 성과 분석 테스트")
    print("=" * 80)

    # Check if running interactively
    is_interactive = sys.stdin.isatty()

    now = datetime.now(KST)
    default_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    default_end = now.strftime("%Y-%m-%d")

    if is_interactive:
      start_date = input(
          f"시작일 입력 (YYYY-MM-DD, 기본값: {default_start}): ").strip() or default_start
      end_date = input(
          f"종료일 입력 (YYYY-MM-DD, 기본값: {default_end}): ").strip() or default_end

      ai_provider_input = input(
          "AI 모델 선택 (gemini/claude/ollama, 기본값: claude): ").strip().lower()
      ai_provider = ai_provider_input if ai_provider_input in [
          "gemini", "claude", "ollama"] else "claude"
    else:
      # Non-interactive mode
      start_date = sys.argv[1] if len(sys.argv) > 1 else default_start
      end_date = sys.argv[2] if len(sys.argv) > 2 else default_end
      ai_provider = sys.argv[3] if len(sys.argv) > 3 else "claude"

      logger.info(f"🤖 Non-interactive mode detected")
      logger.info(f"  시작일: {start_date}")
      logger.info(f"  종료일: {end_date}")
      logger.info(f"  AI: {ai_provider}")

    print("\n" + "=" * 80)
    logger.info(f"🚀 배치 성과 분석 시작")
    logger.info(f"  기간: {start_date} ~ {end_date}")
    logger.info(f"  AI: {ai_provider.upper()}")
    print("=" * 80 + "\n")

    # Progress callback
    async def progress_callback(status: str, current: int, total: int):
      logger.info(f"⏳ {status} [{current}/{total}]")

    # Get agent and analyze
    agent = get_achievement_agent(ai_provider_type=ai_provider)
    result = await agent.analyze_work_logs_batch(
        database_id=work_log_db_id,
        start_date=start_date,
        end_date=end_date,
        progress_callback=progress_callback
    )

    # Print results
    print("\n" + "=" * 80)
    print("✅ 배치 분석 완료!")
    print("=" * 80)
    print(f"\n📆 기간: {start_date} ~ {end_date}")
    print(f"🤖 AI: {ai_provider.upper()}")
    print(f"📊 총 업무일지: {result.get('total', 0)}개")
    print(f"✅ 분석 성공: {result.get('analyzed', 0)}개")
    print(f"❌ 분석 실패: {result.get('failed', 0)}개")

    # Print summary
    results_list = result.get('results', [])
    total_achievements = sum(
        r.get('achievements_count', 0) for r in results_list if r.get('success'))

    print(f"🎯 추출된 총 성과: {total_achievements}개")

    print("\n" + "=" * 80)
    print("✨ Notion에서 확인하세요!")
    print("=" * 80 + "\n")

  except Exception as e:
    logger.error(f"❌ 테스트 실패: {e}", exc_info=True)


async def main():
  """메인 함수"""
  print("\n" + "=" * 80)
  print("성과 분석 테스트")
  print("=" * 80)
  print("1. 단일 페이지 분석")
  print("2. 배치 분석 (기간 지정)")
  print("=" * 80)

  # Check if running interactively
  is_interactive = sys.stdin.isatty()

  if is_interactive:
    choice = input("선택 (1 또는 2): ").strip()
  else:
    # Non-interactive mode: default to single page
    choice = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ["1", "2"] else "1"
    logger.info(f"🤖 Non-interactive mode: choice={choice}")

  if choice == "1":
    await test_single_page()
  elif choice == "2":
    await test_batch_analysis()
  else:
    logger.error("❌ 잘못된 선택입니다!")


if __name__ == "__main__":
  asyncio.run(main())
