import logging
import os

from dotenv import load_dotenv
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Slack AsyncApp
app = AsyncApp(
    token=os.getenv("SLACK_BOT_TOKEN"),
)

# Register all handlers from modules
from src import register_all_handlers
from src.schedule import get_scheduler

# Register handlers
register_all_handlers(app)
logger.info("✅ Handlers registered successfully")

# Initialize scheduler
scheduler = get_scheduler(app)
logger.info("✅ Scheduler initialized")


async def main():
  """Start the Socket Mode handler and scheduler"""
  logger.info("🚀 Starting Secretary Slack Bot...")

  # Start scheduler
  scheduler.start()

  handler = AsyncSocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
  await handler.start_async()


if __name__ == "__main__":
  import asyncio

  asyncio.run(main())
