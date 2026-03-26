import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

# Попытка импорта для разных версий aiogram
try:
    from aiogram.client.default import DefaultBotProperties
    USE_DEFAULT_PROPERTIES = True
except ImportError:
    USE_DEFAULT_PROPERTIES = False

from config import BOT_TOKEN
from database import db
from handlers import router
from admin import admin_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def main():
    try:
        # Подключение к БД
        logger.info("📡 Connecting to database...")
        await db.connect()
        logger.info("✅ Database connected!")
        
        # Инициализация бота
        logger.info("🤖 Initializing bot...")
        
        if USE_DEFAULT_PROPERTIES:
            # Для aiogram 3.2.0+
            bot = Bot(
                token=BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
            )
        else:
            # Для старых версий aiogram 3.x
            bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)
        
        dp = Dispatcher()
        
        # Подключаем роутеры
        dp.include_router(admin_router)
        dp.include_router(router)
        
        logger.info("✅ Bot initialized!")
        logger.info("🚀 Starting polling...")
        
        # Удаляем вебхук если был
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запуск
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)
