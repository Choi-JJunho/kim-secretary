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

    # 데이터베이스 ID (기본값, 유저별로 오버라이드 가능)
    self.wake_up_database_id = os.getenv("NOTION_WAKE_UP_DATABASE_ID")
    self.resume_content_database_id = os.getenv("NOTION_RESUME_CONTENT_DB_ID")

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
      # Build request body
      request_body = {}
      if filter_params:
        request_body["filter"] = filter_params

      # Use the correct API: POST /v1/databases/{database_id}/query
      import httpx
      headers = {
        "Authorization": f"Bearer {self.api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
      }

      async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=headers,
            json=request_body,
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()

      results = data.get("results", [])
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

  # ===== Weekly/Monthly Report Helper Methods =====

  async def query_work_logs_by_date_range(
      self,
      database_id: str,
      start_date: str,
      end_date: str
  ) -> List[Dict[str, Any]]:
    """
    날짜 범위로 업무일지 조회

    Args:
        database_id: 업무일지 데이터베이스 ID
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)

    Returns:
        업무일지 페이지 목록
    """
    try:
      filter_params = {
        "and": [
          {
            "property": "작성일",
            "date": {"on_or_after": start_date}
          },
          {
            "property": "작성일",
            "date": {"on_or_before": end_date}
          }
        ]
      }

      results = await self.query_database(
          database_id=database_id,
          filter_params=filter_params
      )

      logger.info(
          f"📅 업무일지 조회 완료: {start_date} ~ {end_date} ({len(results)}개)")
      return results

    except Exception as e:
      logger.error(f"❌ 업무일지 조회 실패: {e}")
      raise

  async def query_weekly_reports_by_month(
      self,
      database_id: str,
      year: int,
      month: int
  ) -> List[Dict[str, Any]]:
    """
    월별로 주간 리포트 조회

    Args:
        database_id: 주간 리포트 데이터베이스 ID
        year: 연도
        month: 월 (1-12)

    Returns:
        주간 리포트 페이지 목록
    """
    try:
      # 월의 첫날과 마지막날 계산
      from calendar import monthrange
      last_day = monthrange(year, month)[1]
      start_date = f"{year}-{month:02d}-01"
      end_date = f"{year}-{month:02d}-{last_day}"

      filter_params = {
        "and": [
          {
            "property": "시작일",
            "date": {"on_or_after": start_date}
          },
          {
            "property": "시작일",
            "date": {"on_or_before": end_date}
          }
        ]
      }

      results = await self.query_database(
          database_id=database_id,
          filter_params=filter_params
      )

      logger.info(f"📅 주간 리포트 조회 완료: {year}-{month:02d} ({len(results)}개)")
      return results

    except Exception as e:
      logger.error(f"❌ 주간 리포트 조회 실패: {e}")
      raise

  async def create_relation(
      self,
      page_id: str,
      property_name: str,
      target_page_ids: List[str],
      silent: bool = False
  ):
    """
    페이지 간 Relation 생성

    Args:
        page_id: 소스 페이지 ID
        property_name: Relation 속성 이름
        target_page_ids: 연결할 페이지 ID 목록
        silent: True일 경우 실패 시 에러 로그 억제 (선택적 Relation용)
    """
    try:
      properties = {
        property_name: {
          "relation": [{"id": target_id} for target_id in target_page_ids]
        }
      }

      # Notion API 직접 호출 (update_page 우회하여 중복 에러 로그 방지)
      await self.client.pages.update(page_id=page_id, properties=properties)
      logger.info(
          f"🔗 Relation 생성 완료: {page_id} -> {len(target_page_ids)}개 연결")

    except Exception as e:
      if not silent:
        logger.error(f"❌ Relation 생성 실패: {e}")
      raise
