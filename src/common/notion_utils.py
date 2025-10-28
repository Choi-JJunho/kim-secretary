"""Notion 관련 공통 유틸리티 함수"""

import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def get_user_database_mapping(user_id: str) -> Optional[Dict[str, str]]:
  """
  환경 변수에서 유저의 데이터베이스 매핑 정보를 가져옵니다.

  Args:
      user_id: Slack User ID

  Returns:
      유저의 데이터베이스 매핑 정보 (alias, work_log_db, weekly_report_db, etc.)
      또는 None (유저를 찾을 수 없는 경우)

  Raises:
      ValueError: JSON 파싱 실패 시
  """
  user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")

  try:
    user_db_mapping = json.loads(user_db_mapping_str)
  except json.JSONDecodeError as e:
    logger.error(f"❌ Failed to parse NOTION_USER_DATABASE_MAPPING: {e}")
    raise ValueError(f"Invalid NOTION_USER_DATABASE_MAPPING format: {e}")

  user_dbs = user_db_mapping.get(user_id)

  if not user_dbs:
    logger.warning(f"⚠️ No database mapping found for user: {user_id}")
    return None

  return user_dbs


async def extract_page_content(
    notion_client: "NotionClient",
    page_id: str,
    format: str = "text"
) -> str:
  """
  Notion 페이지의 본문 내용을 추출합니다.

  Args:
      notion_client: NotionClient 인스턴스
      page_id: Notion page ID
      format: 출력 형식 ("text" 또는 "markdown")

  Returns:
      페이지 본문 텍스트

  Example:
      >>> content = await extract_page_content(client, "page-id", "text")
      >>> md_content = await extract_page_content(client, "page-id", "markdown")
  """
  try:
    blocks_response = await notion_client.client.blocks.children.list(
        block_id=page_id
    )
    blocks = blocks_response.get("results", [])

    content_parts = []

    for block in blocks:
      block_type = block.get("type")
      block_content = block.get(block_type, {})

      # Handle rich_text blocks
      if "rich_text" in block_content:
        for text_obj in block_content["rich_text"]:
          if "text" in text_obj:
            text = text_obj["text"]["content"]

            # Format based on block type if markdown requested
            if format == "markdown":
              if block_type == "heading_1":
                text = f"# {text}"
              elif block_type == "heading_2":
                text = f"## {text}"
              elif block_type == "heading_3":
                text = f"### {text}"
              elif block_type == "bulleted_list_item":
                text = f"- {text}"
              elif block_type == "numbered_list_item":
                text = f"1. {text}"

            content_parts.append(text)

    separator = "\n" if format == "text" else "\n\n"
    return separator.join(content_parts)

  except Exception as e:
    logger.error(f"❌ Failed to extract page content: {e}")
    return ""


async def find_title_property(
    notion_client: "NotionClient",
    database_id: str,
    fallback: str = "이름"
) -> str:
  """
  데이터베이스에서 title 타입의 속성 이름을 찾습니다.

  Args:
      notion_client: NotionClient 인스턴스
      database_id: Database ID
      fallback: title 속성을 찾지 못했을 때 사용할 기본값

  Returns:
      Title 속성의 이름
  """
  try:
    db_info = await notion_client.get_database(database_id)
    properties = db_info.get("properties", {})

    for prop_name, prop_data in properties.items():
      if prop_data.get("type") == "title":
        logger.info(f"📌 Title 속성 발견: '{prop_name}'")
        return prop_name

    logger.info(f"⚠️ Title 속성을 찾을 수 없어 기본값 사용: '{fallback}'")
    return fallback

  except Exception as e:
    logger.warning(f"⚠️ Title 속성 조회 실패: {e}, 기본값 사용: '{fallback}'")
    return fallback
