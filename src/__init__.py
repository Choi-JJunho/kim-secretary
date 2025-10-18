"""Secretary Slack Bot - Main Package"""

from .chat import register_chat_handlers
from .commands import register_slash_commands
from .commands.work_log_webhook_handler import register_work_log_webhook_handler
from .qa import register_qa_handlers

__all__ = [
  "register_chat_handlers",
  "register_qa_handlers",
  "register_slash_commands",
  "register_work_log_webhook_handler",
  "register_all_handlers",
]


def register_all_handlers(app):
  """Register all handlers to the app"""
  register_chat_handlers(app)
  register_qa_handlers(app)
  register_slash_commands(app)
  register_work_log_webhook_handler(app)
