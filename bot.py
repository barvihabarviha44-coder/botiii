import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import db
from handlers import router
from admin import admin_router
from games import games_router

logging.basicConfig(level=logging.INFO, stream=sys.stdout)


async def main():
    logging.info("📡 Connecting to database...")
    await db.connect()
    logging.info("✅ Database connected!")

    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)

    dp = Dispatcher()
    dp.include_router(admin_router)
    dp.include_router(games_router)
    dp.include_router(router)

    logging.info("🚀 Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
