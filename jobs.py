import random
import asyncio
from config import JOBS_CONFIG, EMOJI
from database import db
from utils import format_coins, create_progress_bar

async def do_work(bot, chat_id: int, user_id: int, job_key: str):
    """Выполнение работы с визуализацией"""
    job = JOBS_CONFIG.get(job_key)
    if not job:
        await bot.send_message(chat_id, f"{EMOJI['cross']} Работа не найдена!")
        return
    
    # Проверка кулдауна
    can = await db.can_work(user_id)
    if not can:
        cooldown = await db.get_work_cooldown(user_id)
        mins = cooldown // 60
        secs = cooldown % 60
        await bot.send_message(
            chat_id, 
            f"{EMOJI['time']} Ты устал! Отдохни ещё **{mins}м {secs}с**"
        )
        return
    
    salary = random.randint(job['min_salary'], job['max_salary'])
    duration = job['duration']
    
    # Начало работы
    msg = await bot.send_message(
        chat_id,
        f"{job['emoji']} **{job['name']}**\n\n"
        f"📋 {job['description']}\n\n"
        f"{create_progress_bar(0, 100)}\n"
        f"💰 Зарплата: {format_coins(salary)}"
    )
    
    # Прогресс работы
    steps = 5
    step_time = duration / steps / 10  # Ускорим для демонстрации
    
    work_messages = {
        'courier': ['📦 Забрал заказ...', '🚴 Еду к клиенту...', '🏃 Бегу по лестнице...', '🔔 Звоню в дверь...', '✅ Заказ доставлен!'],
        'programmer': ['💻 Открыл IDE...', '⌨️ Пишу код...', '🐛 Исправляю баги...', '☕ Перерыв на кофе...', '✅ Проект готов!'],
        'trader': ['📊 Анализирую рынок...', '📈 Открываю позицию...', '😰 Рынок падает...', '🚀 Рост!', '✅ Закрыл в плюс!'],
        'businessman': ['📞 Важный звонок...', '🤝 Встреча с партнёрами...', '📝 Подписание контракта...', '💼 Совещание...', '✅ Сделка закрыта!'],
        'ceo': ['🏢 Приехал в офис...', '📊 Проверка отчётов...', '👔 Совет директоров...', '✈️ Командировка...', '✅ Компания процветает!']
    }
    
    messages = work_messages.get(job_key, ['⏳ Работаю...' for _ in range(5)])
    
    for i in range(1, steps + 1):
        await asyncio.sleep(step_time)
        progress = int(100 * i / steps)
        try:
            await msg.edit_text(
                f"{job['emoji']} **{job['name']}**\n\n"
                f"📋 {messages[i-1]}\n\n"
                f"{create_progress_bar(progress, 100)}\n"
                f"💰 Зарплата: {format_coins(salary)}"
            )
        except:
            pass
    
    # Выплата зарплаты
    await db.update_coins(user_id, salary)
    await db.set_work_time(user_id)
    
    await msg.edit_text(
        f"{job['emoji']} **{job['name']}** - Завершено!\n\n"
        f"✅ {messages[-1]}\n\n"
        f"{create_progress_bar(100, 100)}\n"
        f"💰 Получено: **{format_coins(salary)}**"
    )
