import re
from aiogram import Router, F
from aiogram.types import Message
from config import ADMIN_IDS
from database import db
from utils import format_number, format_coins, format_vibeton

admin_router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(F.text.lower().in_(['админ', 'admin']))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    text = (
        "🔐 **АДМИН-ПАНЕЛЬ**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "**Команды:**\n"
        "`абан 123456` - забанить\n"
        "`аразбан 123456` - разбанить\n"
        "`авыдать 123456 10000` - выдать VC\n"
        "`авыдатьvt 123456 5` - выдать VT\n"
        "`астат 123456` - статистика игрока\n"
        "`апромо КОД 10000 0 100` - создать промо\n"
        "`астатистика` - общая статистика"
    )
    
    await message.answer(text)


@admin_router.message(F.text.lower().startswith('абан'))
async def admin_ban(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: `абан 123456`")
        return
    
    try:
        target_id = int(parts[1])
    except:
        await message.answer("❌ Некорректный ID!")
        return
    
    await db.ban_user(target_id, True)
    await message.answer(f"✅ Пользователь `{target_id}` забанен!")


@admin_router.message(F.text.lower().startswith('аразбан'))
async def admin_unban(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: `аразбан 123456`")
        return
    
    try:
        target_id = int(parts[1])
    except:
        await message.answer("❌ Некорректный ID!")
        return
    
    await db.ban_user(target_id, False)
    await message.answer(f"✅ Пользователь `{target_id}` разбанен!")


@admin_router.message(F.text.lower().startswith('авыдатьvt'))
async def admin_give_vt(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❌ Использование: `авыдатьvt 123456 5`")
        return
    
    try:
        target_id = int(parts[1])
        amount = float(parts[2])
    except:
        await message.answer("❌ Некорректные данные!")
        return
    
    await db.update_vibeton(target_id, amount)
    await message.answer(f"✅ Выдано **{amount:.2f} VT** → `{target_id}`")


@admin_router.message(F.text.lower().startswith('авыдать'))
async def admin_give(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❌ Использование: `авыдать 123456 10000`")
        return
    
    try:
        target_id = int(parts[1])
        amount = int(parts[2])
    except:
        await message.answer("❌ Некорректные данные!")
        return
    
    await db.update_coins(target_id, amount)
    await message.answer(f"✅ Выдано **{format_number(amount)} VC** → `{target_id}`")


@admin_router.message(F.text.lower().startswith('астат'))
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: `астат 123456`")
        return
    
    try:
        target_id = int(parts[1])
    except:
        await message.answer("❌ Некорректный ID!")
        return
    
    user = await db.get_user(target_id)
    if not user:
        await message.answer("❌ Пользователь не найден!")
        return
    
    text = (
        f"📊 **Игрок:** `{target_id}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {user['first_name']} (@{user['username']})\n"
        f"💎 VC: {format_number(user['coins'])}\n"
        f"🔮 VT: {user['vibeton']:.2f}\n"
        f"🏦 Банк: {format_number(user['bank_balance'])}\n"
        f"🎮 Игр: {user['total_games']}\n"
        f"🏆 Побед: {user['total_wins']}\n"
        f"🚫 Бан: {'Да' if user['is_banned'] else 'Нет'}"
    )
    
    await message.answer(text)


@admin_router.message(F.text.lower().startswith('апромо'))
async def admin_create_promo(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) < 5:
        await message.answer("❌ Использование: `апромо КОД vc vt макс`\nПример: `апромо TEST 10000 0 100`")
        return
    
    try:
        code = parts[1].upper()
        coins = int(parts[2])
        vibeton = float(parts[3])
        max_uses = int(parts[4])
    except:
        await message.answer("❌ Некорректные данные!")
        return
    
    await db.create_promo(code, coins, vibeton, max_uses)
    
    await message.answer(
        f"✅ **Промокод создан!**\n\n"
        f"📝 Код: `{code}`\n"
        f"💎 VC: {format_number(coins)}\n"
        f"🔮 VT: {vibeton:.2f}\n"
        f"👥 Макс: {max_uses}"
    )


@admin_router.message(F.text.lower() == 'астатистика')
async def admin_global_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    stats = await db.get_global_stats()
    
    text = (
        f"📊 **СТАТИСТИКА БОТА**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"🚫 Забанено: {stats['banned_users']}\n"
        f"💎 Всего VC: {format_number(stats['total_coins'])}\n"
        f"🔮 Всего VT: {stats['total_vibeton']:.2f}\n"
        f"🎮 Всего игр: {stats['total_games']}"
    )
    
    await message.answer(text)
