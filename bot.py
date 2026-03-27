import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import db
from handlers import router
from admin import admin_router
from games import games_router

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))


async def president_scheduler(bot: Bot):
    while True:
        try:
            now = datetime.now(MSK)

            if now.hour == 0 and now.minute == 7:
                processed, result = await db.process_president_election()

                if processed:
                    winner = await db.get_user(result)
                    winner_name = winner["username"] or winner["first_name"] or str(result)

                    logger.info(f"President election processed. Winner: {winner_name}")

                    # Уведомление всем пользователям из топа/активным не делаем массово через БД списка,
                    # чтобы не ломать производительность. Можно расширить позже.
                elif result == "no_participants":
                    logger.info("President election: no participants")
                elif result == "already_processed":
                    pass

                await asyncio.sleep(60)

            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"President scheduler error: {e}")
            await asyncio.sleep(10)


async def main():
    logger.info("📡 Connecting to database...")
    await db.connect()
    logger.info("✅ Database connected!")

    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)

    dp = Dispatcher()
    dp.include_router(admin_router)
    dp.include_router(games_router)
    dp.include_router(router)

    logger.info("🚀 Bot starting...")

    asyncio.create_task(president_scheduler(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
