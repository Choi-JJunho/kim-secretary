"""Q&A and assistant event handlers"""

import logging

logger = logging.getLogger(__name__)


def register_qa_handlers(app):
  """Register all Q&A and assistant-related handlers"""

  @app.event("app_mention")
  async def handle_app_mention(event, say, logger):
    """Handle @mention events"""
    user = event.get("user")
    logger.info(f"🔔 Mention from <@{user}>")
    await say(f"안녕하세요 <@{user}>! 무엇을 도와드릴까요? 🤖")
