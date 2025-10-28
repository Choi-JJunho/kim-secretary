"""모든 리포트 데이터베이스 자동 초기화"""

import asyncio
import json
import logging
import os
import sys

from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.notion.client import NotionClient
from src.notion.db_initializer import init_notion_db, add_relation_property
from src.notion.db_schema import (
    get_work_log_schema,
    get_weekly_report_schema,
    get_monthly_report_schema
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def init_all_databases():
  """모든 리포트 데이터베이스 초기화"""
  try:
    load_dotenv()

    # Get user database mapping
    user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")
    if not user_db_mapping_str or user_db_mapping_str == "{}":
      logger.error("❌ NOTION_USER_DATABASE_MAPPING 환경 변수가 설정되지 않았습니다!")
      return False

    user_db_mapping = json.loads(user_db_mapping_str)
    if not user_db_mapping:
      logger.error("❌ 데이터베이스 매핑이 비어있습니다!")
      return False

    user_id = list(user_db_mapping.keys())[0]
    user_dbs = user_db_mapping[user_id]

    user_alias = user_dbs.get("alias", "이름없음")
    work_log_db_id = user_dbs.get("work_log_db")
    weekly_report_db_id = user_dbs.get("weekly_report_db")
    monthly_report_db_id = user_dbs.get("monthly_report_db")

    logger.info(f"📋 사용자: {user_alias} ({user_id})")
    logger.info(f"  Work Log DB: {work_log_db_id}")
    logger.info(f"  Weekly Report DB: {weekly_report_db_id}")
    logger.info(f"  Monthly Report DB: {monthly_report_db_id}")

    print("\n" + "=" * 80)
    print("🚀 데이터베이스 초기화 시작")
    print("=" * 80 + "\n")

    client = NotionClient()
    success_count = 0
    total_count = 0

    # 1. 업무일지 DB 초기화
    if work_log_db_id:
      total_count += 1
      logger.info("\n📝 1/3: 업무일지 DB 초기화 중...")
      schema = get_work_log_schema()
      if await init_notion_db(work_log_db_id, schema, notion_client=client):
        success_count += 1
        logger.info("✅ 업무일지 DB 초기화 완료!")

    # 2. 주간 리포트 DB 초기화
    if weekly_report_db_id:
      total_count += 1
      logger.info("\n📅 2/3: 주간 리포트 DB 초기화 중...")
      schema = get_weekly_report_schema()
      if await init_notion_db(weekly_report_db_id, schema, notion_client=client):
        success_count += 1
        logger.info("✅ 주간 리포트 DB 초기화 완료!")

        # 업무일지 DB와 Relation 추가
        if work_log_db_id:
          logger.info("🔗 업무일지 DB와 Relation 연결 중...")
          await add_relation_property(
              source_db_id=weekly_report_db_id,
              target_db_id=work_log_db_id,
              relation_name="일지목록",
              reverse_name="주간리포트",
              notion_client=client
          )

    # 3. 월간 리포트 DB 초기화
    if monthly_report_db_id:
      total_count += 1
      logger.info("\n📊 3/3: 월간 리포트 DB 초기화 중...")
      schema = get_monthly_report_schema()
      if await init_notion_db(monthly_report_db_id, schema, notion_client=client):
        success_count += 1
        logger.info("✅ 월간 리포트 DB 초기화 완료!")

        # 주간 리포트 DB와 Relation 추가
        if weekly_report_db_id:
          logger.info("🔗 주간 리포트 DB와 Relation 연결 중...")
          await add_relation_property(
              source_db_id=monthly_report_db_id,
              target_db_id=weekly_report_db_id,
              relation_name="주간리포트",
              reverse_name="월간리포트",
              notion_client=client
          )

    # 결과 출력
    print("\n" + "=" * 80)
    if success_count == total_count:
      print("🎉 모든 데이터베이스 초기화 완료!")
    else:
      print(f"⚠️ 일부 데이터베이스 초기화 실패 ({success_count}/{total_count} 성공)")
    print("=" * 80)

    print("\n다음 단계:")
    print("1. Notion에서 각 데이터베이스를 열어 속성이 정상적으로 생성되었는지 확인")
    print("2. 테스트 스크립트 실행:")
    print("   - 주간 리포트: python3 scripts/test_weekly_report.py 2025 43")
    print("   - 월간 리포트: python3 scripts/test_monthly_report.py 2025 10")
    print()

    return success_count == total_count

  except Exception as e:
    logger.error(f"❌ 초기화 실패: {e}", exc_info=True)
    return False


if __name__ == "__main__":
  asyncio.run(init_all_databases())
