# main.py

import os
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app.config import BOT_TOKEN, WEBAPP_URL, PORT
from app.handlers import common, time_tracker, reports, admin, life_tracker, habits
from app.services.scheduler_service import start_scheduler, shutdown_scheduler
from app.webapp import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application):
    """
    Lifespan context manager for FastAPI:
    Initializes Telegram Bot, sets chat menu button, starts nightly scheduler,
    and runs aiogram polling concurrently with the web server.
    """
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured in environment variables.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Register routers
    dp.include_router(common.router)
    dp.include_router(time_tracker.router)
    dp.include_router(reports.router)
    dp.include_router(admin.router)
    dp.include_router(life_tracker.router)
    dp.include_router(habits.router)

    # Set persistent Telegram Chat Menu Button if WEBAPP_URL is configured
    if WEBAPP_URL:
        try:
            logger.info(f"Setting Chat Menu Button to Mini App URL: {WEBAPP_URL}")
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="📱 ثبت سریع",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
            )
        except Exception as e:
            logger.warning(f"Could not set chat menu button: {e}")

    # Start Nightly Scheduler
    start_scheduler(bot)

    # Start Bot Polling as background task
    logger.info("Starting Telegram Bot Polling task...")
    polling_task = asyncio.create_task(dp.start_polling(bot))

    try:
        yield
    finally:
        logger.info("Shutting down bot and scheduler...")
        shutdown_scheduler()
        await dp.stop_polling()
        polling_task.cancel()
        try:
            await polling_task
        except (asyncio.CancelledError, Exception):
            pass
        await bot.session.close()
        logger.info("Bot and scheduler successfully stopped.")


# Attach lifespan to FastAPI app
app.router.lifespan_context = lifespan


def main():
    port = int(os.getenv("PORT", PORT))
    logger.info(f"Starting NotionYar WebApp & Bot on 0.0.0.0:{port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()