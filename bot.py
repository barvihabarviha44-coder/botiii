import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database import db
from handlers import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Подключение к БД
    await db.connect()
    logger.info("Database connected!")
    
    # Инициализация бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    
    dp = Dispatcher()
    dp.include_router(router)
    
    # Запуск бота
    logger.info("Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
