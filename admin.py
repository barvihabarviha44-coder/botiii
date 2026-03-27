from aiogram import Router, F
from aiogram.types import Message
from config import ADMIN_IDS
from database import db
from utils import format_num

admin_router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@admin_router.message(F.text.lower().in_(["админ", "admin"]))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "🔐 **АДМИНКА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "`абан ID` — бан\n"
        "`аразбан ID` — разбан\n"
        "`авыдать ID сумма` — выдать VC\n"
        "`авыдатьvt ID сумма` — выдать VT\n"
        "`астат ID` — инфо игрока\n"
        "`апромо КОД VC VT uses` — создать промо\n"
        "`астатистика` — статистика бота"
    )


@admin_router.message(F.text.lower().startswith("абан "))
async def admin_ban(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Укажи ID")
        return

    try:
        target_id = int(parts[1])
    except:
        await message.answer("❌ ID неверный")
        return

    await db.ban_user(target_id, True)
    await message.answer(f"✅ Пользователь `{target_id}` забанен")


@admin_router.message(F.text.lower().startswith("аразбан "))
async def admin_unban(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Укажи ID")
        return

    try:
        target_id = int(parts[1])
    except:
        await message.answer("❌ ID неверный")
        return

    await db.ban_user(target_id, False)
    await message.answer(f"✅ Пользователь `{target_id}` разбанен")


@admin_router.message(F.text.lower().startswith("авыдатьvt "))
async def admin_give_vt(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❌ Использование: авыдатьvt ID сумма")
        return

    try:
        target_id = int(parts[1])
        amount = float(parts[2].replace(",", "."))
    except:
        await message.answer("❌ Ошибка данных")
        return

    user = await db.get_user(target_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return

    await db.update_vibeton(target_id, amount)
    await message.answer(f"✅ Выдано **{amount:.2f} VT** → `{target_id}`")


@admin_router.message(F.text.lower().startswith("авыдать "))
async def admin_give_vc(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❌ Использование: авыдать ID сумма")
        return

    try:
        target_id = int(parts[1])
        amount = int(parts[2])
    except:
        await message.answer("❌ Ошибка данных")
        return

    user = await db.get_user(target_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return

    await db.update_coins(target_id, amount)
    await message.answer(f"✅ Выдано **{format_num(amount)} VC** → `{target_id}`")


@admin_router.message(F.text.lower().startswith("астат "))
async def admin_user_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: астат ID")
        return

    try:
        target_id = int(parts[1])
    except:
        await message.answer("❌ ID неверный")
        return

    user = await db.get_user(target_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return

    await message.answer(
        f"📊 **ИГРОК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 `{user['user_id']}`\n"
        f"👤 {user['first_name']} (@{user['username']})\n\n"
        f"💎 **{format_num(user['coins'])}** VC\n"
        f"🔮 **{user['vibeton']:.2f}** VT\n"
        f"🏦 **{format_num(user['bank_balance'])}** VC\n"
        f"⭐ XP: **{user['xp']}**\n\n"
        f"🎮 Игр: **{user['total_games']}**\n"
        f"🏆 Побед: **{user['total_wins']}**\n"
        f"📈 Выиграл: **{format_num(user['total_earned'])}** VC\n"
        f"📉 Слил: **{format_num(user['total_lost'])}** VC\n"
        f"🚫 Бан: **{'Да' if user['is_banned'] else 'Нет'}**"
    )


@admin_router.message(F.text.lower().startswith("апромо "))
async def admin_create_promo(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 5:
        await message.answer("❌ Использование: апромо КОД VC VT uses")
        return

    try:
        code = parts[1].upper()
        coins = int(parts[2])
        vibeton = float(parts[3].replace(",", "."))
        uses = int(parts[4])
    except:
        await message.answer("❌ Ошибка данных")
        return

    await db.create_promo(code, coins, vibeton, uses)
    await message.answer(
        f"✅ **ПРОМО СОЗДАН**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎁 `{code}`\n"
        f"💎 {format_num(coins)} VC\n"
        f"🔮 {vibeton:.2f} VT\n"
        f"👥 Использований: {uses}"
    )


@admin_router.message(F.text.lower() == "астатистика")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = await db.get_global_stats()

    await message.answer(
        f"📊 **СТАТИСТИКА БОТА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Пользователей: **{stats['total_users']}**\n"
        f"🚫 В бане: **{stats['banned_users']}**\n"
        f"💎 Всего VC: **{format_num(stats['total_coins'])}**\n"
        f"🔮 Всего VT: **{stats['total_vibeton']:.2f}**\n"
        f"🎮 Всего игр: **{stats['total_games']}**"
    )
