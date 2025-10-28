"""기상 관리 Notion 매니저"""

import logging
import os
from datetime import datetime
from typing import Optional

import pytz

from .client import NotionClient

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


class WakeUpManager:
  """Manager for wake-up tracking in Notion database"""

  def __init__(self, client: Optional[NotionClient] = None):
    """Initialize WakeUpManager with NotionClient"""
    self.client = client or NotionClient()
    self.database_id = os.getenv("NOTION_WAKE_UP_DATABASE_ID")

    if not self.database_id:
      raise ValueError(
          "NOTION_WAKE_UP_DATABASE_ID environment variable is required")

  async def get_database_schema(self) -> dict:
    """
    Get wake-up database schema for debugging

    Returns:
      dict: Database schema information
    """
    try:
      db_info = await self.client.get_database(self.database_id)
      logger.info("=" * 80)
      logger.info("📚 WAKE-UP DATABASE SCHEMA:")
      logger.info("=" * 80)

      properties = db_info.get("properties", {})
      for prop_name, prop_info in properties.items():
        prop_type = prop_info.get("type")
        logger.info(f"  - {prop_name}: {prop_type}")
        logger.info(f"    Full info: {prop_info}")

      logger.info("=" * 80)
      return db_info
    except Exception as e:
      logger.error(f"❌ Failed to get database schema: {e}")
      raise

  async def get_wake_up_count(self, user_id: str) -> int:
    """
    특정 사용자의 기상 기록 개수 조회

    Args:
      user_id: Slack user ID

    Returns:
      int: 기상 기록 개수
    """
    try:
      filter_params = {
        "property": "사용자 아이디",
        "rich_text": {
          "equals": user_id
        }
      }
      results = await self.client.query_database(
          database_id=self.database_id,
          filter_params=filter_params
      )
      count = len(results)
      logger.info(f"📊 {user_id}의 기상 기록: {count}개")
      return count
    except Exception as e:
      logger.error(f"❌ Failed to get wake-up count: {e}")
      return 0

  async def record_wake_up(
      self,
      user_id: str,
      user_name: Optional[str] = None,
      wake_up_time: Optional[datetime] = None,
  ) -> dict:
    """
    Record wake-up time in Notion database

    Args:
      user_id: Slack user ID
      user_name: Slack user display name (optional)
      wake_up_time: Wake-up timestamp (defaults to now)

    Returns:
      dict: Created page response from Notion
    """
    # First, get and log the database schema
    await self.get_database_schema()

    if wake_up_time is None:
      wake_up_time = datetime.now(KST)
    elif wake_up_time.tzinfo is None:
      # If no timezone info, assume it's KST
      wake_up_time = KST.localize(wake_up_time)

    # Match the actual Notion DB schema (Korean field names)
    properties = {
      "사용자 이름": {"title": [{"text": {"content": user_name or user_id}}]},
      "사용자 아이디": {"rich_text": [{"text": {"content": user_id}}]},
      "확인 시각": {"date": {"start": wake_up_time.isoformat()}},
      "날짜": {"date": {"start": wake_up_time.date().isoformat()}},
      "상태": {"select": {"name": "성공"}},
    }

    logger.info("🔍 Attempting to create page with properties:")
    logger.info(f"  Properties: {properties}")

    try:
      page = await self.client.create_page(self.database_id, properties)
      logger.info(f"✅ Wake-up recorded for user {user_id} at {wake_up_time}")
      return page
    except Exception as e:
      logger.error(f"❌ Failed to record wake-up: {e}")
      raise


# Singleton instance
_wake_up_manager: Optional[WakeUpManager] = None


def get_wake_up_manager() -> WakeUpManager:
  """Get or create singleton WakeUpManager instance"""
  global _wake_up_manager
  if _wake_up_manager is None:
    _wake_up_manager = WakeUpManager()
  return _wake_up_manager
