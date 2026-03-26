import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database import db
from handlers import router
from admin import admin_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def main():
    try:
        # Подключение к БД
        logger.info("Connecting to database...")
        await db.connect()
        logger.info("✅ Database connected successfully!")
        
        # Инициализация бота
        logger.info("Initializing bot...")
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        
        dp = Dispatcher()
        dp.include_router(admin_router)  # Админ роутер первым
        dp.include_router(router)
        
        logger.info("✅ Bot initialized successfully!")
        
        # Запуск бота
        logger.info("🚀 Bot is starting...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.error(f"❌ Error starting bot: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
