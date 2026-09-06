# main.py

import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.config import BOT_TOKEN
from app.handlers import common, time_tracker, reports, admin, life_tracker, habits
from app.services.scheduler_service import start_scheduler, shutdown_scheduler

logging.basicConfig(level=logging.INFO)


async def main():
    if BOT_TOKEN is None:
        raise RuntimeError("BOT_TOKEN is not configured")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Register routers
    dp.include_router(common.router)
    dp.include_router(time_tracker.router)
    dp.include_router(reports.router)
    dp.include_router(admin.router)
    dp.include_router(life_tracker.router)
    dp.include_router(habits.router)

    # Start Nightly Scheduler
    start_scheduler(bot)

    try:
        print("Bot is starting polling...")
        await dp.start_polling(bot)
    finally:
        shutdown_scheduler()


if __name__ == "__main__":
    asyncio.run(main())