"""Slash command handlers"""

import logging

logger = logging.getLogger(__name__)


def register_slash_commands(app):
  """Register all slash command handlers"""

  @app.command("/상태")
  async def handle_status_command(ack, respond):
    """Handle /status command"""
    await ack()
    await respond("저는 건강합니다! ✅")
