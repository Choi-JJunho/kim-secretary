"""Notion 데이터베이스 현재 스키마 확인 스크립트"""

import argparse
import asyncio
import json
import logging
import os
import sys

from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.notion.client import NotionClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_notion_url(url: str) -> str:
  """Notion URL에서 데이터베이스 ID 추출"""
  import re
  match = re.search(r'([a-f0-9]{32})', url)
  if not match:
    raise ValueError(f"올바른 Notion URL이 아닙니다: {url}")

  db_id = match.group(1)
  formatted_id = f"{db_id[0:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:32]}"
  return formatted_id


async def inspect_database(database_id: str):
  """데이터베이스 스키마 상세 조회"""
  try:
    load_dotenv()

    client = NotionClient()

    logger.info(f"🔍 데이터베이스 조회 중...")
    logger.info(f"📍 Database ID: {database_id}")

    # 데이터베이스 정보 조회
    db_info = await client.get_database(database_id)

    # 기본 정보 출력
    title = db_info.get('title', [{}])[0].get('plain_text', 'Untitled')
    logger.info(f"\n📊 데이터베이스 이름: {title}")
    logger.info(f"🆔 ID: {db_info.get('id')}")
    logger.info(f"🔗 URL: {db_info.get('url')}")

    # 속성 정보 출력
    properties = db_info.get('properties', {})
    logger.info(f"\n📋 현재 속성 개수: {len(properties)}")
    logger.info(f"\n속성 상세:")
    logger.info("=" * 80)

    for prop_name, prop_data in properties.items():
      prop_type = prop_data.get('type')
      logger.info(f"\n속성명: {prop_name}")
      logger.info(f"  타입: {prop_type}")
      logger.info(f"  ID: {prop_data.get('id')}")

      # 타입별 상세 정보
      if prop_type == 'multi_select':
        options = prop_data.get('multi_select', {}).get('options', [])
        logger.info(f"  옵션 개수: {len(options)}")
        for opt in options:
          logger.info(f"    - {opt.get('name')} (색상: {opt.get('color')})")

      elif prop_type == 'select':
        options = prop_data.get('select', {}).get('options', [])
        logger.info(f"  옵션 개수: {len(options)}")
        for opt in options:
          logger.info(f"    - {opt.get('name')} (색상: {opt.get('color')})")

      elif prop_type == 'relation':
        relation_data = prop_data.get('relation', {})
        logger.info(f"  연결 DB ID: {relation_data.get('database_id')}")
        logger.info(f"  타입: {relation_data.get('type')}")

    logger.info("\n" + "=" * 80)

    # JSON 출력 (디버깅용)
    logger.info("\n🔍 전체 스키마 (JSON):")
    print(json.dumps(properties, indent=2, ensure_ascii=False))

    return True

  except Exception as e:
    logger.error(f"❌ 조회 실패: {e}")
    import traceback
    traceback.print_exc()
    return False


async def main():
  parser = argparse.ArgumentParser(description="Notion 데이터베이스 스키마 확인")
  parser.add_argument("--db-id", required=True, help="Notion 데이터베이스 ID 또는 URL")

  args = parser.parse_args()

  # DB ID 파싱
  try:
    if "notion.so" in args.db_id:
      db_id = parse_notion_url(args.db_id)
      logger.info(f"📋 URL에서 DB ID 추출: {db_id}")
    else:
      db_id = args.db_id
  except Exception as e:
    logger.error(f"❌ DB ID 파싱 실패: {e}")
    return

  await inspect_database(db_id)


if __name__ == "__main__":
  asyncio.run(main())
