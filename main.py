# main.py

import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.config import BOT_TOKEN
from app.handlers import common, time_tracker, reports, admin, life_tracker

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

    print("Bot is starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())