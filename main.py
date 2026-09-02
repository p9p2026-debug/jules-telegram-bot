"""
Main Application Entrypoint for Jules Telegram Bot.
Initializes Database, starts Async HTTP Health-Check Server (for Render),
registers command/message/callback handlers, and launches Telegram Bot polling.
"""

import asyncio
import logging
import signal
import sys

# Ensure UTF-8 output encoding across Windows and POSIX systems
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

from telegram.ext import ApplicationBuilder
import config
from database.db import init_db
from handlers.admin_handlers import register_admin_handlers
from handlers.error_handlers import error_handler
from handlers.user_handlers import register_user_handlers
from utils.server import start_health_server

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("jules_bot")

async def run_bot() -> None:
    """Initializes and runs the bot alongside the health check server."""
    logger.info("Starting Jules by Google Telegram Bot...")

    # Validate essential environment variables
    if not config.BOT_TOKEN:
        logger.critical(
            "❌ [CONFIG ERROR] BOT_TOKEN is missing! "
            "Please configure BOT_TOKEN in your .env file or Render Environment Variables."
        )
        sys.exit(1)

    if not config.GEMINI_API_KEY:
        logger.warning(
            "⚠️ [WARNING] GEMINI_API_KEY is not configured in environment! "
            "Users will need to provide their own key via /apikey, or admin can set it."
        )

    # 1. Initialize Database
    logger.info("Initializing SQLite database at: %s", config.DATABASE_PATH)
    await init_db()

    # 2. Start Async HTTP Health Server (Render compatibility)
    health_server = None
    try:
        health_server = await start_health_server(config.HOST, config.PORT)
    except Exception as exc:
        logger.error("Failed to start health server on port %s: %s", config.PORT, exc)

    # 3. Build Telegram Application
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # 4. Register Handlers
    register_admin_handlers(app)
    register_user_handlers(app)
    app.add_error_handler(error_handler)

    # 5. Start Polling with Async Context Manager
    logger.info("Connecting to Telegram Bot API and starting polling...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("🤖 Bot is successfully ONLINE and listening for updates!")

        # Keep running until interrupt signal
        stop_event = asyncio.Event()

        # Handle Unix termination signals if available
        loop = asyncio.get_running_loop()
        for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
            if sig is not None:
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except (NotImplementedError, RuntimeError):
                    pass

        try:
            while not stop_event.is_set():
                await asyncio.sleep(1.0)
        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("Termination signal received. Shutting down gracefully...")

        logger.info("Stopping Telegram polling...")
        await app.updater.stop()
        await app.stop()

        if health_server:
            logger.info("Stopping health check server...")
            health_server.close()
            await health_server.wait_closed()

    logger.info("Jules Bot has cleanly stopped.")


def main():
    """Main process entrypoint."""
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application exited.")
    except Exception as exc:
        logger.exception("Fatal crash in main process: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
