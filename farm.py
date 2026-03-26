from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import GPU_CONFIG, EMOJI
from database import db
from utils import format_coins, format_vibeton

async def get_farm_info(user_id: int) -> str:
    """Получение информации о ферме"""
    gpus = await db.get_user_gpus(user_id)
    farm_stats = await db.get_farm_stats(user_id)
    
    total_per_hour = 0
    gpu_list = ""
    
    for gpu_key, gpu_info in GPU_CONFIG.items():
        user_gpu = next((g for g in gpus if g['gpu_type'] == gpu_key), None)
        count = user_gpu['count'] if user_gpu else 0
        production = count * gpu_info['vibe_per_hour']
        total_per_hour += production
        
        current_price = await db.get_gpu_price(user_id, gpu_key, gpu_info['base_price'])
        
        gpu_list += (
            f"{gpu_info['emoji']} **{gpu_info['name']}**\n"
            f"   📊 Количество: {count}/10\n"
            f"   ⚡ Добыча: {production:.1f} VT/час\n"
            f"   💰 Цена: {format_coins(current_price)}\n\n"
        )
    
    # Расчет накопленного
    if farm_stats and farm_stats['last_collect']:
        elapsed = datetime.utcnow() - farm_stats['last_collect']
        hours = elapsed.total_seconds() / 3600
        accumulated = total_per_hour * hours
    else:
        accumulated = 0
    
    return (
        f"{EMOJI['farm']} **ФЕРМА VIBETON**\n"
        f"{'═' * 25}\n\n"
        f"{gpu_list}"
        f"{'─' * 25}\n"
        f"⚡ Общая добыча: **{total_per_hour:.1f} VT/час**\n"
        f"💎 Накоплено: **{accumulated:.2f} VT**\n"
        f"📈 Всего добыто: **{farm_stats['total_mined']:.2f} VT**"
    )

def get_farm_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура фермы"""
    keyboard = [
        [InlineKeyboardButton(text="🟢 Купить GTX 1660", callback_data="buy_gpu_gtx1660")],
        [InlineKeyboardButton(text="🟡 Купить RTX 3070", callback_data="buy_gpu_rtx3070")],
        [InlineKeyboardButton(text="🔴 Купить RTX 4090", callback_data="buy_gpu_rtx4090")],
        [InlineKeyboardButton(text="💎 Собрать VibeTon", callback_data="collect_farm")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_farm")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def collect_vibeton(user_id: int) -> tuple:
    """Сбор накопленного VibeTon"""
    gpus = await db.get_user_gpus(user_id)
    farm_stats = await db.get_farm_stats(user_id)
    
    total_per_hour = sum(
        (next((g['count'] for g in gpus if g['gpu_type'] == k), 0) * v['vibe_per_hour'])
        for k, v in GPU_CONFIG.items()
    )
    
    if not farm_stats or not farm_stats['last_collect']:
        return 0, "no_farm"
    
    elapsed = datetime.utcnow() - farm_stats['last_collect']
    hours = elapsed.total_seconds() / 3600
    accumulated = total_per_hour * hours
    
    if accumulated < 0.01:
        return 0, "too_early"
    
    await db.collect_farm(user_id, accumulated)
    return accumulated, "success"
