"""
Notion 주간/월간 리포트 데이터베이스 스키마 초기화 스크립트

Usage:
    python scripts/init_report_databases.py --type weekly --db-id <database_id>
    python scripts/init_report_databases.py --type monthly --db-id <database_id>
    python scripts/init_report_databases.py --type work-log --db-id <database_id>
"""

import argparse
import asyncio
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_weekly_report_schema():
  """주간 리포트 DB 스키마 정의 (title 제외)"""
  return {
    "시작일": {
      "date": {}
    },
    "종료일": {
      "date": {}
    },
    "요약": {
      "rich_text": {}
    },
    "주요성과": {
      "rich_text": {}
    },
    "사용기술": {
      "multi_select": {
        "options": [
          {"name": "Python", "color": "blue"},
          {"name": "JavaScript", "color": "yellow"},
          {"name": "TypeScript", "color": "blue"},
          {"name": "React", "color": "blue"},
          {"name": "FastAPI", "color": "green"},
          {"name": "Django", "color": "green"},
          {"name": "PostgreSQL", "color": "blue"},
          {"name": "Redis", "color": "red"},
          {"name": "Docker", "color": "blue"},
          {"name": "AWS", "color": "orange"},
          {"name": "Git", "color": "gray"}
        ]
      }
    },
    "배운점": {
      "rich_text": {}
    },
    "개선점": {
      "rich_text": {}
    },
    "성과카테고리": {
      "multi_select": {
        "options": [
          {"name": "개발", "color": "blue"},
          {"name": "리더십", "color": "purple"},
          {"name": "협업", "color": "green"},
          {"name": "문제해결", "color": "red"},
          {"name": "학습", "color": "yellow"},
          {"name": "코드리뷰", "color": "pink"},
          {"name": "멘토링", "color": "orange"},
          {"name": "문서화", "color": "gray"}
        ]
      }
    },
    "이력서반영": {
      "checkbox": {}
    },
    "AI 생성 완료": {
      "select": {
        "options": [
          {"name": "완료", "color": "green"},
          {"name": "미완료", "color": "gray"}
        ]
      }
    }
  }


def get_monthly_report_schema():
  """월간 리포트 DB 스키마 정의 (title 제외)"""
  return {
    "시작일": {
      "date": {}
    },
    "종료일": {
      "date": {}
    },
    "월간요약": {
      "rich_text": {}
    },
    "핵심성과": {
      "rich_text": {}
    },
    "기술성장": {
      "rich_text": {}
    },
    "리더십경험": {
      "rich_text": {}
    },
    "문제해결사례": {
      "rich_text": {}
    },
    "역량분석": {
      "rich_text": {}
    },
    "다음달목표": {
      "rich_text": {}
    },
    "AI 생성 완료": {
      "select": {
        "options": [
          {"name": "완료", "color": "green"},
          {"name": "미완료", "color": "gray"}
        ]
      }
    }
  }


def get_work_log_additional_properties():
  """업무일지 DB에 추가할 속성들"""
  return {
    "정량적성과": {
      "rich_text": {}
    },
    "성과타입": {
      "select": {
        "options": [
          {"name": "개발", "color": "blue"},
          {"name": "리뷰", "color": "purple"},
          {"name": "회의", "color": "green"},
          {"name": "학습", "color": "yellow"},
          {"name": "기타", "color": "gray"}
        ]
      }
    },
    "기술스택": {
      "multi_select": {
        "options": [
          {"name": "Python", "color": "blue"},
          {"name": "JavaScript", "color": "yellow"},
          {"name": "TypeScript", "color": "blue"},
          {"name": "React", "color": "blue"},
          {"name": "FastAPI", "color": "green"},
          {"name": "Django", "color": "green"},
          {"name": "PostgreSQL", "color": "blue"},
          {"name": "Redis", "color": "red"},
          {"name": "Docker", "color": "blue"},
          {"name": "AWS", "color": "orange"},
          {"name": "Git", "color": "gray"}
        ]
      }
    },
    "프로젝트": {
      "select": {
        "options": [
          {"name": "메인 프로젝트", "color": "blue"},
          {"name": "사이드 프로젝트", "color": "green"},
          {"name": "인프라", "color": "orange"},
          {"name": "기타", "color": "gray"}
        ]
      }
    }
  }


async def init_database_schema(database_id: str, schema: dict, db_type: str, title_name: str = None):
  """
  Notion 데이터베이스 스키마 초기화

  Args:
      database_id: Notion 데이터베이스 ID
      schema: 초기화할 스키마 정의
      db_type: 데이터베이스 타입 (weekly/monthly/work-log)
      title_name: Title 속성의 새 이름 (None이면 변경 안 함)
  """
  try:
    load_dotenv()

    # NotionClient 초기화
    client = NotionClient()

    logger.info(f"🔄 {db_type} 데이터베이스 스키마 초기화 시작...")
    logger.info(f"📍 Database ID: {database_id}")

    # 기존 DB 정보 조회
    try:
      db_info = await client.get_database(database_id)
      logger.info(f"✅ 데이터베이스 연결 성공: {db_info.get('title', [{}])[0].get('plain_text', 'Untitled')}")

      # 기존 title 속성 찾기
      existing_props = db_info.get('properties', {})
      title_prop_name = None
      for prop_name, prop_data in existing_props.items():
        if prop_data.get('type') == 'title':
          title_prop_name = prop_name
          logger.info(f"📌 기존 Title 속성 발견: '{prop_name}'")
          break

    except Exception as e:
      logger.error(f"❌ 데이터베이스 연결 실패: {e}")
      logger.error("데이터베이스 ID가 올바른지, Notion API 키가 해당 DB에 접근 권한이 있는지 확인하세요.")
      return False

    # Title 속성 이름 변경 (필요한 경우)
    if title_name and title_prop_name and title_prop_name != title_name:
      logger.info(f"📝 Title 속성 이름 변경: '{title_prop_name}' → '{title_name}'")
      try:
        await client.client.databases.update(
            database_id=database_id,
            properties={
              title_prop_name: {
                "name": title_name
              }
            }
        )
        logger.info(f"✅ Title 속성 이름 변경 완료")
      except Exception as e:
        logger.warning(f"⚠️ Title 속성 이름 변경 실패: {e}")

    # 나머지 스키마 업데이트
    try:
      logger.info(f"📊 {len(schema)}개 속성 생성 중...")

      # 디버깅: 요청 데이터 출력
      import json
      logger.info(f"🔍 전송할 스키마:")
      logger.info(json.dumps(schema, indent=2, ensure_ascii=False))

      response = await client.client.databases.update(
          database_id=database_id,
          properties=schema
      )

      # 디버깅: 응답 확인
      logger.info(f"🔍 API 응답:")
      logger.info(json.dumps(response, indent=2, ensure_ascii=False))

      # 결과 확인
      updated_props = response.get('properties', {})
      logger.info(f"✅ 스키마 업데이트 완료!")
      logger.info(f"📊 현재 총 속성 개수: {len(updated_props)}")

      # 생성된 속성 목록 출력
      logger.info(f"📋 API 응답의 속성 목록:")
      for prop_name, prop_data in updated_props.items():
        prop_type = prop_data.get('type')
        logger.info(f"  - {prop_name} ({prop_type})")

      return True

    except Exception as e:
      logger.error(f"❌ 스키마 업데이트 실패: {e}")
      import traceback
      traceback.print_exc()
      return False

  except Exception as e:
    logger.error(f"❌ 초기화 실패: {e}")
    import traceback
    traceback.print_exc()
    return False


async def add_relation_properties(
    source_db_id: str,
    target_db_id: str,
    relation_name: str,
    reverse_name: str = None
):
  """
  두 데이터베이스 간 Relation 속성 추가

  Args:
      source_db_id: 소스 DB ID
      target_db_id: 타겟 DB ID
      relation_name: Relation 속성 이름
      reverse_name: 역방향 Relation 이름 (optional)
  """
  try:
    load_dotenv()
    client = NotionClient()

    logger.info(f"🔗 Relation 속성 추가: {relation_name}")

    # Relation 속성 정의
    relation_config = {
      "relation": {
        "database_id": target_db_id,
        "type": "dual_property" if reverse_name else "single_property"
      }
    }

    if reverse_name:
      relation_config["relation"]["dual_property"] = {
        "synced_property_name": reverse_name
      }

    # 소스 DB에 Relation 추가
    await client.client.databases.update(
        database_id=source_db_id,
        properties={
          relation_name: relation_config
        }
    )

    logger.info(f"✅ Relation 속성 '{relation_name}' 추가 완료!")
    return True

  except Exception as e:
    logger.error(f"❌ Relation 추가 실패: {e}")
    return False


def parse_notion_url(url: str) -> str:
  """
  Notion URL에서 데이터베이스 ID 추출

  Args:
      url: Notion 데이터베이스 URL

  Returns:
      데이터베이스 ID (하이픈 형식)
  """
  # URL에서 ID 부분 추출
  # 예: https://www.notion.so/workspace/29ab3645abb580ea9bb1dcb7310735c7?v=...
  import re

  # URL에서 32자리 16진수 추출
  match = re.search(r'([a-f0-9]{32})', url)
  if not match:
    raise ValueError(f"올바른 Notion URL이 아닙니다: {url}")

  db_id = match.group(1)

  # 하이픈 형식으로 변환 (8-4-4-4-12)
  formatted_id = f"{db_id[0:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:32]}"

  return formatted_id


async def main():
  parser = argparse.ArgumentParser(
      description="Notion 리포트 데이터베이스 스키마 초기화"
  )
  parser.add_argument(
      "--type",
      required=True,
      choices=["weekly", "monthly", "work-log"],
      help="데이터베이스 타입"
  )
  parser.add_argument(
      "--db-id",
      required=True,
      help="Notion 데이터베이스 ID 또는 URL"
  )
  parser.add_argument(
      "--work-log-db",
      help="업무일지 DB ID (주간 리포트에 Relation 추가 시 필요)"
  )
  parser.add_argument(
      "--weekly-report-db",
      help="주간 리포트 DB ID (월간 리포트에 Relation 추가 시 필요)"
  )

  args = parser.parse_args()

  # DB ID 파싱 (URL이면 ID 추출)
  try:
    if "notion.so" in args.db_id:
      db_id = parse_notion_url(args.db_id)
      logger.info(f"📋 URL에서 DB ID 추출: {db_id}")
    else:
      db_id = args.db_id
  except Exception as e:
    logger.error(f"❌ DB ID 파싱 실패: {e}")
    return

  # 데이터베이스 타입에 따라 스키마 선택
  if args.type == "weekly":
    schema = get_weekly_report_schema()
    success = await init_database_schema(db_id, schema, "주간 리포트", title_name="주차")

    # 업무일지 DB와 Relation 추가 (옵션)
    if success and args.work_log_db:
      logger.info("\n🔗 업무일지 DB와 Relation 연결 중...")
      await add_relation_properties(
          source_db_id=db_id,
          target_db_id=args.work_log_db,
          relation_name="일지목록",
          reverse_name="주간리포트"
      )

  elif args.type == "monthly":
    schema = get_monthly_report_schema()
    success = await init_database_schema(db_id, schema, "월간 리포트", title_name="월")

    # 주간 리포트 DB와 Relation 추가 (옵션)
    if success and args.weekly_report_db:
      logger.info("\n🔗 주간 리포트 DB와 Relation 연결 중...")
      await add_relation_properties(
          source_db_id=db_id,
          target_db_id=args.weekly_report_db,
          relation_name="주간리포트",
          reverse_name="월간리포트"
      )

  elif args.type == "work-log":
    schema = get_work_log_additional_properties()
    success = await init_database_schema(db_id, schema, "업무일지 (속성 추가)", title_name=None)

  if success:
    logger.info("\n🎉 데이터베이스 초기화 완료!")
    logger.info("\n다음 단계:")
    logger.info("1. Notion에서 데이터베이스를 열어 속성이 정상적으로 생성되었는지 확인하세요")
    logger.info("2. .env 파일에 데이터베이스 ID를 설정하세요")
    logger.info(f"   예: NOTION_USER_DATABASE_MAPPING='{{\"USER_ID\":{{\"alias\":\"홍길동\",\"work_log_db\":\"{args.work_log_db or 'xxxxx'}\",\"weekly_report_db\":\"{db_id}\"}}}}'")
  else:
    logger.error("\n❌ 초기화 실패")
    sys.exit(1)


if __name__ == "__main__":
  asyncio.run(main())
