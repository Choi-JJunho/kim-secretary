"""Notion 데이터베이스 자동 초기화 모듈"""

import logging
from typing import Dict, Any, Optional

from .client import NotionClient

logger = logging.getLogger(__name__)


async def init_notion_db(
    database_id: str,
    schema: Dict[str, Any],
    title_property_name: Optional[str] = None,
    notion_client: Optional[NotionClient] = None
) -> bool:
  """
  Notion 데이터베이스 자동 초기화

  Args:
      database_id: Notion 데이터베이스 ID
      schema: 추가할 속성 스키마 (title 속성 제외)
      title_property_name: Title 속성의 원하는 이름 (None이면 변경 안 함)
      notion_client: NotionClient 인스턴스 (None이면 새로 생성)

  Returns:
      성공 여부

  Example:
      schema = {
          "시작일": {"date": {}},
          "종료일": {"date": {}},
          "AI 생성 완료": {"select": {"options": [{"name": "완료", "color": "green"}]}}
      }
      success = await init_notion_db(db_id, schema, title_property_name="주차")
  """
  client = notion_client or NotionClient()

  try:
    logger.info(f"🔄 데이터베이스 초기화 시작: {database_id}")

    # 1. 기존 DB 정보 조회
    try:
      db_info = await client.get_database(database_id)
      db_title = db_info.get('title', [{}])[0].get('plain_text', 'Untitled')
      logger.info(f"✅ 데이터베이스 연결: {db_title}")
    except Exception as e:
      logger.error(f"❌ 데이터베이스 연결 실패: {e}")
      return False

    # 2. 기존 title 속성 찾기
    existing_props = db_info.get('properties', {})
    current_title_prop = None
    for prop_name, prop_data in existing_props.items():
      if prop_data.get('type') == 'title':
        current_title_prop = prop_name
        logger.info(f"📌 기존 Title 속성: '{prop_name}'")
        break

    # Title 속성이 없으면 기본값 확인
    if not current_title_prop:
      # 빈 DB의 경우 첫 페이지 생성 시 title 속성이 생성됨
      logger.info("⚠️ Title 속성을 찾을 수 없음 (빈 DB일 수 있음)")
      current_title_prop = "이름"  # Notion 한국어 기본값

    # 3. Title 속성 이름 변경 (필요한 경우)
    if title_property_name and current_title_prop != title_property_name:
      logger.info(f"📝 Title 속성 이름 변경 시도: '{current_title_prop}' → '{title_property_name}'")
      try:
        # 기존 속성이 실제로 존재하는 경우에만 이름 변경
        if existing_props.get(current_title_prop):
          await client.client.databases.update(
              database_id=database_id,
              properties={
                current_title_prop: {
                  "name": title_property_name
                }
              }
          )
          logger.info(f"✅ Title 속성 이름 변경 완료")
        else:
          logger.info(f"⚠️ 기존 Title 속성이 없어 이름 변경 스킵")
      except Exception as e:
        logger.warning(f"⚠️ Title 속성 이름 변경 실패 (계속 진행): {e}")

    # 4. 나머지 속성 추가
    if schema:
      logger.info(f"📊 {len(schema)}개 속성 추가 중...")
      try:
        await client.client.databases.update(
            database_id=database_id,
            properties=schema
        )
        logger.info(f"✅ 스키마 속성 추가 완료")
      except Exception as e:
        logger.error(f"❌ 속성 추가 실패: {e}")
        return False

    logger.info(f"🎉 데이터베이스 초기화 완료: {database_id}")
    return True

  except Exception as e:
    logger.error(f"❌ 초기화 실패: {e}")
    return False


async def add_relation_property(
    source_db_id: str,
    target_db_id: str,
    relation_name: str,
    reverse_name: Optional[str] = None,
    notion_client: Optional[NotionClient] = None
) -> bool:
  """
  두 데이터베이스 간 Relation 속성 추가

  Args:
      source_db_id: Relation을 추가할 소스 DB ID
      target_db_id: Relation이 가리킬 타겟 DB ID
      relation_name: 소스 DB의 Relation 속성 이름
      reverse_name: 타겟 DB의 역방향 Relation 속성 이름 (dual property)
      notion_client: NotionClient 인스턴스 (None이면 새로 생성)

  Returns:
      성공 여부
  """
  client = notion_client or NotionClient()

  try:
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

    logger.info(f"✅ Relation '{relation_name}' 추가 완료")
    return True

  except Exception as e:
    logger.error(f"❌ Relation 추가 실패: {e}")
    return False


async def ensure_db_schema(
    database_id: str,
    schema: Dict[str, Any],
    title_property_name: Optional[str] = None,
    notion_client: Optional[NotionClient] = None
) -> bool:
  """
  데이터베이스 스키마 확인 및 필요시 초기화

  DB가 이미 초기화되어 있으면 스킵하고, 없으면 초기화합니다.

  Args:
      database_id: Notion 데이터베이스 ID
      schema: 필요한 속성 스키마
      title_property_name: Title 속성의 원하는 이름
      notion_client: NotionClient 인스턴스

  Returns:
      성공 여부
  """
  client = notion_client or NotionClient()

  try:
    db_info = await client.get_database(database_id)
    existing_props = db_info.get('properties', {})

    # 데이터베이스 뷰인지 확인 (data_sources가 있으면 뷰)
    is_view = len(db_info.get('data_sources', [])) > 0

    if is_view:
      logger.info(f"📋 데이터베이스 뷰 감지: {database_id}")
      logger.info(f"⏭️  스키마 초기화 스킵 (뷰는 소스 DB의 스키마를 상속)")
      return True

    # 필요한 속성이 모두 있는지 확인
    missing_props = {}
    for prop_name, prop_schema in schema.items():
      if prop_name not in existing_props:
        missing_props[prop_name] = prop_schema

    if not missing_props and len(existing_props) > 0:
      logger.info(f"✅ 데이터베이스 스키마 이미 초기화됨: {database_id}")
      return True

    # 누락된 속성만 추가
    if missing_props:
      logger.info(f"📊 {len(missing_props)}개 누락 속성 추가 중...")
      return await init_notion_db(database_id, missing_props, title_property_name, client)

    # 속성이 하나도 없으면 전체 초기화
    logger.info(f"📊 데이터베이스 전체 초기화 중...")
    return await init_notion_db(database_id, schema, title_property_name, client)

  except Exception as e:
    logger.error(f"❌ 스키마 확인 실패: {e}")
    return False
