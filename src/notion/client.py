"""Notion API 클라이언트 래퍼"""

import logging
import os
from typing import Any, Dict, List, Optional

from notion_client import AsyncClient

logger = logging.getLogger(__name__)


class NotionClient:
  """Notion 비동기 클라이언트 래퍼"""

  def __init__(self):
    """환경 변수에서 API 키를 읽어 Notion 클라이언트 초기화"""
    self.api_key = os.getenv("NOTION_API_KEY")
    if not self.api_key:
      raise ValueError("NOTION_API_KEY 환경 변수가 설정되지 않았습니다")

    self.client = AsyncClient(auth=self.api_key)

    # 데이터베이스 ID
    self.wake_up_database_id = os.getenv("NOTION_WAKE_UP_DATABASE_ID")
    self.task_database_id = os.getenv("NOTION_TASK_DATABASE_ID")
    self.routine_database_id = os.getenv("NOTION_ROUTINE_DATABASE_ID")

    logger.info("✅ Notion 클라이언트 초기화 완료")

  async def query_database(
      self,
      database_id: Optional[str] = None,
      filter_params: Optional[Dict] = None
  ) -> List[Dict[str, Any]]:
    """
    데이터베이스 조회

    Args:
        database_id: 데이터베이스 ID (없으면 기본값 사용)
        filter_params: 필터 조건

    Returns:
        페이지 목록
    """
    db_id = database_id or self.wake_up_database_id
    if not db_id:
      raise ValueError("데이터베이스 ID가 제공되지 않았습니다")

    try:
      query_params = {"database_id": db_id}
      if filter_params:
        query_params["filter"] = filter_params

      response = await self.client.databases.query(**query_params)
      results = response.get("results", [])
      logger.info(f"📊 데이터베이스 조회 완료: {len(results)}개 결과")
      return results
    except Exception as e:
      logger.error(f"❌ 데이터베이스 조회 실패: {e}")
      raise

  async def create_page(
      self,
      database_id: Optional[str] = None,
      properties: Optional[Dict[str, Any]] = None,
      content: Optional[List[Dict[str, Any]]] = None,
  ) -> Dict[str, Any]:
    """
    데이터베이스에 새 페이지 생성

    Args:
        database_id: 데이터베이스 ID (없으면 기본값 사용)
        properties: 페이지 속성
        content: 페이지 콘텐츠 블록

    Returns:
        생성된 페이지 객체
    """
    db_id = database_id or self.wake_up_database_id
    if not db_id:
      raise ValueError("데이터베이스 ID가 제공되지 않았습니다")

    try:
      page_data = {
        "parent": {"database_id": db_id},
        "properties": properties or {}
      }

      if content:
        page_data["children"] = content

      response = await self.client.pages.create(**page_data)
      logger.info(f"✅ 페이지 생성 완료: {response['id']}")
      return response
    except Exception as e:
      logger.error(f"❌ 페이지 생성 실패: {e}")
      raise

  async def update_page(
      self,
      page_id: str,
      properties: Dict[str, Any]
  ) -> Dict[str, Any]:
    """
    페이지 속성 업데이트

    Args:
        page_id: 페이지 ID
        properties: 업데이트할 속성

    Returns:
        업데이트된 페이지 객체
    """
    try:
      response = await self.client.pages.update(
          page_id=page_id,
          properties=properties
      )
      logger.info(f"✅ 페이지 업데이트 완료: {page_id}")
      return response
    except Exception as e:
      logger.error(f"❌ 페이지 업데이트 실패: {e}")
      raise

  async def delete_page(self, page_id: str) -> Dict[str, Any]:
    """
    페이지 아카이브 (소프트 삭제)

    Args:
        page_id: 아카이브할 페이지 ID

    Returns:
        아카이브된 페이지 객체
    """
    try:
      response = await self.client.pages.update(
          page_id=page_id,
          archived=True
      )
      logger.info(f"🗑️ 페이지 아카이브 완료: {page_id}")
      return response
    except Exception as e:
      logger.error(f"❌ 페이지 아카이브 실패: {e}")
      raise

  async def get_page(self, page_id: str) -> Dict[str, Any]:
    """
    특정 페이지 조회

    Args:
        page_id: 조회할 페이지 ID

    Returns:
        페이지 객체
    """
    try:
      response = await self.client.pages.retrieve(page_id=page_id)
      logger.info(f"📄 페이지 조회 완료: {page_id}")
      return response
    except Exception as e:
      logger.error(f"❌ 페이지 조회 실패: {e}")
      raise

  async def get_database(
      self,
      database_id: Optional[str] = None
  ) -> Dict[str, Any]:
    """
    데이터베이스 메타데이터 조회

    Args:
        database_id: 데이터베이스 ID (없으면 기본값 사용)

    Returns:
        데이터베이스 객체
    """
    db_id = database_id or self.wake_up_database_id
    if not db_id:
      raise ValueError("데이터베이스 ID가 제공되지 않았습니다")

    try:
      response = await self.client.databases.retrieve(database_id=db_id)
      logger.info(f"📚 데이터베이스 조회 완료: {db_id}")
      return response
    except Exception as e:
      logger.error(f"❌ 데이터베이스 조회 실패: {e}")
      raise
