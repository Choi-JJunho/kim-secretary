"""Notion integration module for Secretary bot"""

from .client import NotionClient
from .wake_up import WakeUpManager

__all__ = ["NotionClient", "WakeUpManager"]

# Singleton instance for easy access
_client = None


def get_notion_client() -> NotionClient:
  """Get or create Notion client instance"""
  global _client
  if _client is None:
    _client = NotionClient()
  return _client
