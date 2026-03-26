import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import db
from handlers import router
from admin import admin_router

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def main():
    logger.info("📡 Connecting to database...")
    await db.connect()
    logger.info("✅ Database connected!")
    
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)
    
    dp = Dispatcher()
    dp.include_router(admin_router)
    dp.include_router(router)
    
    logger.info("🚀 Bot starting...")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
