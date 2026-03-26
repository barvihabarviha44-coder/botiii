import re
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import EMOJI, ADMIN_IDS
from utils import format_coins, format_vibeton, format_number

admin_router = Router()

class AdminStates(StatesGroup):
    waiting_broadcast_message = State()
    waiting_promo_code = State()
    waiting_promo_coins = State()
    waiting_promo_vibeton = State()
    waiting_promo_uses = State()
    waiting_give_user = State()
    waiting_give_amount = State()
    waiting_give_currency = State()
    waiting_set_user = State()
    waiting_set_amount = State()
    waiting_set_currency = State()

def is_admin(user_id: int) -> bool:
    """Проверка на админа"""
    return user_id in ADMIN_IDS

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура админ-панели"""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton(text="💰 Выдать валюту", callback_data="admin_give"),
            InlineKeyboardButton(text="📝 Установить баланс", callback_data="admin_set")
        ],
        [
            InlineKeyboardButton(text="🎁 Промокоды", callback_data="admin_promos"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="🔨 Бан/Разбан", callback_data="admin_ban_menu"),
            InlineKeyboardButton(text="🔍 Поиск игрока", callback_data="admin_search")
        ],
        [
            InlineKeyboardButton(text="💹 Управление рынком", callback_data="admin_market"),
            InlineKeyboardButton(text="🗑 Сброс данных", callback_data="admin_reset")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ==================== ГЛАВНОЕ МЕНЮ АДМИНКИ ====================

@admin_router.message(F.text.lower().in_(['админ', 'admin', 'апанель', 'админка']))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    text = (
        f"🔐 **АДМИН-ПАНЕЛ��**\n"
        f"{'═' * 30}\n\n"
        f"👋 Добро пожаловать, администратор!\n\n"
        f"Выберите действие:"
    )
    
    await message.answer(text, reply_markup=get_admin_keyboard())


@admin_router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await state.clear()
    
    text = (
        f"🔐 **АДМИН-ПАНЕЛЬ**\n"
        f"{'═' * 30}\n\n"
        f"👋 Добро пожаловать, администратор!\n\n"
        f"Выберите действие:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard())


# ==================== СТАТИСТИКА ====================

@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    stats = await db.get_global_stats()
    
    text = (
        f"📊 **ГЛОБАЛЬНАЯ СТАТИСТИКА**\n"
        f"{'═' * 30}\n\n"
        f"👥 **Пользователи:**\n"
        f"   • Всего: {stats['total_users']}\n"
        f"   • Активных (24ч): {stats['active_24h']}\n"
        f"   • Забанено: {stats['banned_users']}\n\n"
        f"💰 **Экономика:**\n"
        f"   • Всего VC в игре: {format_coins(stats['total_coins'])}\n"
        f"   • Всего VT в игре: {format_vibeton(stats['total_vibeton'])}\n"
        f"   • В банках: {format_coins(stats['total_bank'])}\n\n"
        f"🎮 **Игры:**\n"
        f"   • Всего игр: {format_number(stats['total_games'])}\n"
        f"   • Выиграно: {format_coins(stats['total_won'])}\n"
        f"   • Проиграно: {format_coins(stats['total_lost'])}\n\n"
        f"⛏️ **Майнинг:**\n"
        f"   • Всего видеокарт: {stats['total_gpus']}\n"
        f"   • Добыто VT: {format_vibeton(stats['total_mined'])}\n\n"
        f"🛒 **Рынок:**\n"
        f"   • Активных ордеров: {stats['active_orders']}\n"
        f"   • Текущий курс: {format_coins(stats['current_price'])}/VT"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@admin_router.message(F.text.lower() == 'астатистика')
async def admin_global_stats_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    stats = await db.get_global_stats()
    
    text = (
        f"📊 **ГЛОБАЛЬНАЯ СТАТИСТИКА**\n"
        f"{'═' * 30}\n\n"
        f"👥 Всего пользователей: **{stats['total_users']}**\n"
        f"🚫 Забанено: **{stats['banned_users']}**\n\n"
        f"💎 Всего VC: **{format_coins(stats['total_coins'])}**\n"
        f"🔮 Всего VT: **{format_vibeton(stats['total_vibeton'])}**\n"
        f"🏦 В банках: **{format_coins(stats['total_bank'])}**\n\n"
        f"🎮 Всего игр: **{format_number(stats['total_games'])}**"
    )
    
    await message.answer(text)


# ==================== ПОЛЬЗОВАТЕЛИ ====================

@admin_router.callback_query(F.data == "admin_users")
async def admin_users_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    top_users = await db.get_top_coins(10)
    
    text = f"👥 **ТОП-10 БОГАТЫХ ИГРОКОВ**\n{'═' * 30}\n\n"
    
    for i, user in enumerate(top_users, 1):
        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"{i}."))
        name = user['first_name'] or user['username'] or 'Аноним'
        banned = " 🚫" if user.get('is_banned') else ""
        text += f"{medal} `{user['user_id']}` - {name}{banned}\n"
        text += f"    💰 {format_coins(user['coins'])}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 По VC", callback_data="admin_users_coins"),
            InlineKeyboardButton(text="🔮 По VT", callback_data="admin_users_vt")
        ],
        [InlineKeyboardButton(text="🔍 Поиск игрока", callback_data="admin_search")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@admin_router.callback_query(F.data == "admin_users_vt")
async def admin_users_vt_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    top_users = await db.get_top_vibeton(10)
    
    text = f"👥 **ТОП-10 ПО VIBETON**\n{'═' * 30}\n\n"
    
    for i, user in enumerate(top_users, 1):
        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"{i}."))
        name = user['first_name'] or user['username'] or 'Аноним'
        text += f"{medal} `{user['user_id']}` - {name}\n"
        text += f"    🔮 {format_vibeton(user['vibeton'])}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 По VC", callback_data="admin_users_coins"),
            InlineKeyboardButton(text="🔮 По VT", callback_data="admin_users_vt")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


# ==================== ПОИСК И ПРОСМОТР ИГРОКА ====================

@admin_router.callback_query(F.data == "admin_search")
async def admin_search_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        f"🔍 **ПОИСК ИГРОКА**\n\n"
        f"Введите ID или @username игрока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_back")]
        ])
    )
    
    await state.set_state(AdminStates.waiting_give_user)
    await state.update_data(action="search")


@admin_router.message(F.text.lower().regexp(r'^астат\s+(.+)$'))
async def admin_user_stats_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    match = re.match(r'^астат\s+(.+)$', message.text.lower())
    identifier = match.group(1).strip().replace('@', '')
    
    # Поиск по ID или username
    if identifier.isdigit():
        user = await db.get_user(int(identifier))
    else:
        user = await db.get_user_by_username(identifier)
    
    if not user:
        await message.answer(f"{EMOJI['cross']} Пользователь не найден!")
        return
    
    await send_user_info(message, user)


async def send_user_info(message: Message, user: dict):
    """Отправка подробной информации о пользователе"""
    winrate = (user['total_wins'] / user['total_games'] * 100) if user['total_games'] > 0 else 0
    
    # Получаем данные о ферме
    gpus = await db.get_user_gpus(user['user_id'])
    total_gpus = sum(g['count'] for g in gpus) if gpus else 0
    
    # Получаем данные о рынке
    orders = await db.get_user_market_orders(user['user_id'])
    active_orders = len([o for o in orders if o['is_active']]) if orders else 0
    
    text = (
        f"👤 **ИНФОРМАЦИЯ О ИГРОКЕ**\n"
        f"{'═' * 30}\n\n"
        f"🆔 **ID:** `{user['user_id']}`\n"
        f"📛 **Имя:** {user['first_name'] or 'Не указано'}\n"
        f"👤 **Username:** @{user['username'] or 'нет'}\n"
        f"🚫 **Бан:** {'❌ Да' if user['is_banned'] else '✅ Нет'}\n"
        f"📅 **Регистрация:** {user['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        
        f"{'─' * 30}\n"
        f"💰 **БАЛАНС:**\n"
        f"   💎 VC: {format_coins(user['coins'])}\n"
        f"   🔮 VT: {format_vibeton(user['vibeton'])}\n"
        f"   🏦 Банк: {format_coins(user['bank_balance'])}\n\n"
        
        f"{'─' * 30}\n"
        f"🎮 **СТАТИСТИКА ИГР:**\n"
        f"   📊 Всего игр: {user['total_games']}\n"
        f"   🏆 Побед: {user['total_wins']}\n"
        f"   📈 Винрейт: {winrate:.1f}%\n"
        f"   💰 Заработано: {format_coins(user['total_earned'])}\n"
        f"   💸 Проиграно: {format_coins(user['total_lost'])}\n\n"
        
        f"{'─' * 30}\n"
        f"⛏️ **ФЕРМА:**\n"
        f"   🖥️ Видеокарт: {total_gpus}\n"
        f"   📋 Ордеров на рынке: {active_orders}\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Выдать", callback_data=f"admin_give_{user['user_id']}"),
            InlineKeyboardButton(text="📝 Установить", callback_data=f"admin_set_{user['user_id']}")
        ],
        [
            InlineKeyboardButton(
                text="🔓 Разбанить" if user['is_banned'] else "🔨 Забанить", 
                callback_data=f"admin_toggle_ban_{user['user_id']}"
            )
        ],
        [
            InlineKeyboardButton(text="🗑 Сбросить данные", callback_data=f"admin_reset_user_{user['user_id']}")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


# ==================== БАН/РАЗБАН ====================

@admin_router.callback_query(F.data == "admin_ban_menu")
async def admin_ban_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    # Получаем список забаненных
    banned_users = await db.get_banned_users()
    
    text = f"🔨 **УПРАВЛЕНИЕ БАНАМИ**\n{'═' * 30}\n\n"
    
    if banned_users:
        text += "🚫 **Забаненные пользователи:**\n"
        for user in banned_users[:20]:
            name = user['first_name'] or user['username'] or 'Аноним'
            text += f"   • `{user['user_id']}` - {name}\n"
    else:
        text += "✅ Забаненных пользователей нет\n"
    
    text += "\n📝 Команды:\n"
    text += "• `абан <id>` - забанить\n"
    text += "• `аразбан <id>` - разбанить"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_ban_menu")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@admin_router.message(F.text.lower().regexp(r'^абан\s+(\d+)(?:\s+(.+))?$'))
async def admin_ban_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    match = re.match(r'^абан\s+(\d+)(?:\s+(.+))?$', message.text.lower())
    target_id = int(match.group(1))
    reason = match.group(2) or "Не указана"
    
    user = await db.get_user(target_id)
    if not user:
        await message.answer(f"{EMOJI['cross']} Пользователь не найден!")
        return
    
    if user['is_banned']:
        await message.answer(f"{EMOJI['warning']} Пользователь уже забанен!")
        return
    
    await db.ban_user(target_id, True, reason)
    
    await message.answer(
        f"✅ **Пользователь забанен!**\n\n"
        f"🆔 ID: `{target_id}`\n"
        f"👤 Имя: {user['first_name']}\n"
        f"📝 Причина: {reason}"
    )


@admin_router.message(F.text.lower().regexp(r'^аразбан\s+(\d+)$'))
async def admin_unban_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    match = re.match(r'^аразбан\s+(\d+)$', message.text.lower())
    target_id = int(match.group(1))
    
    user = await db.get_user(target_id)
    if not user:
        await message.answer(f"{EMOJI['cross']} Пользователь не найден!")
        return
    
    if not user['is_banned']:
        await message.answer(f"{EMOJI['warning']} Пользователь не забанен!")
        return
    
    await db.ban_user(target_id, False)
    
    await message.answer(
        f"✅ **Пользователь разбанен!**\n\n"
        f"🆔 ID: `{target_id}`\n"
        f"👤 Имя: {user['first_name']}"
    )


@admin_router.callback_query(F.data.startswith("admin_toggle_ban_"))
async def admin_toggle_ban_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    target_id = int(callback.data.replace("admin_toggle_ban_", ""))
    user = await db.get_user(target_id)
    
    if not user:
        await callback.answer("Пользователь не найден!", show_alert=True)
        return
    
    new_status = not user['is_banned']
    await db.ban_user(target_id, new_status)
    
    status_text = "забанен" if new_status else "разбанен"
    await callback.answer(f"✅ Пользователь {status_text}!", show_alert=True)
    
    # Обновляем информацию
    user = await db.get_user(target_id)
    await send_user_info(callback.message, user)


# ==================== ВЫДАЧА ВАЛЮТЫ ====================

@admin_router.callback_query(F.data == "admin_give")
async def admin_give_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        f"💰 **ВЫДАЧА ВАЛЮТЫ**\n\n"
        f"Введите ID пользователя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_back")]
        ])
    )
    
    await state.set_state(AdminStates.waiting_give_user)
    await state.update_data(action="give")


@admin_router.callback_query(F.data.startswith("admin_give_"))
async def admin_give_user_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    target_id = int(callback.data.replace("admin_give_", ""))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 VC", callback_data=f"admin_give_cur_{target_id}_vc"),
            InlineKeyboardButton(text="🔮 VT", callback_data=f"admin_give_cur_{target_id}_vt")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(
        f"💰 **ВЫДАЧА ВАЛЮТЫ**\n\n"
        f"🆔 Пользователь: `{target_id}`\n\n"
        f"Выберите валюту:",
        reply_markup=keyboard
    )


@admin_router.callback_query(F.data.regexp(r'^admin_give_cur_(\d+)_(vc|vt)$'))
async def admin_give_currency_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    match = re.match(r'^admin_give_cur_(\d+)_(vc|vt)$', callback.data)
    target_id = int(match.group(1))
    currency = match.group(2)
    
    await state.update_data(target_id=target_id, currency=currency)
    await state.set_state(AdminStates.waiting_give_amount)
    
    currency_name = "VineCoin (VC)" if currency == "vc" else "VibeTon (VT)"
    
    await callback.message.edit_text(
        f"💰 **ВЫДАЧА ВАЛЮТЫ**\n\n"
        f"🆔 Пользователь: `{target_id}`\n"
        f"💵 Валюта: {currency_name}\n\n"
        f"Введите сумму:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_back")]
        ])
    )


@admin_router.message(AdminStates.waiting_give_amount)
async def admin_give_amount_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except:
        await message.answer(f"{EMOJI['cross']} Введите корректную сумму!")
        return
    
    target_id = data['target_id']
    currency = data['currency']
    
    if currency == 'vc':
        await db.update_coins(target_id, int(amount))
        await message.answer(
            f"✅ **Успешно выдано!**\n\n"
            f"🆔 Пользователь: `{target_id}`\n"
            f"💎 Сумма: {format_coins(int(amount))}"
        )
    else:
        await db.update_vibeton(target_id, amount)
        await message.answer(
            f"✅ **Успешно выдано!**\n\n"
            f"🆔 Пользователь: `{target_id}`\n"
            f"🔮 Сумма: {format_vibeton(amount)}"
        )
    
    await state.clear()


@admin_router.message(F.text.lower().regexp(r'^авыдать\s+(\d+)\s+([\d.]+)\s*(vc|vt|вк|вт)?$'))
async def admin_give_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    match = re.match(r'^авыдать\s+(\d+)\s+([\d.]+)\s*(vc|vt|вк|вт)?$', message.text.lower())
    target_id = int(match.group(1))
    amount = float(match.group(2))
    currency = match.group(3) or 'vc'
    
    user = await db.get_user(target_id)
    if not user:
        await message.answer(f"{EMOJI['cross']} Пользователь не найден!")
        return
    
    if currency in ['vt', 'вт']:
        await db.update_vibeton(target_id, amount)
        await message.answer(
            f"✅ **Выдано!**\n\n"
            f"👤 {user['first_name']} (`{target_id}`)\n"
            f"🔮 +{format_vibeton(amount)}"
        )
    else:
        await db.update_coins(target_id, int(amount))
        await message.answer(
            f"✅ **Выдано!**\n\n"
            f"👤 {user['first_name']} (`{target_id}`)\n"
            f"💎 +{format_coins(int(amount))}"
        )


# ==================== УСТАНОВКА БАЛАНСА ====================

@admin_router.callback_query(F.data.startswith("admin_set_"))
async def admin_set_user_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    target_id = int(callback.data.replace("admin_set_", ""))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 VC", callback_data=f"admin_setcur_{target_id}_vc"),
            InlineKeyboardButton(text="🔮 VT", callback_data=f"admin_setcur_{target_id}_vt")
        ],
        [
            InlineKeyboardButton(text="🏦 Банк", callback_data=f"admin_setcur_{target_id}_bank")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(
        f"📝 **УСТАНОВКА БАЛАНСА**\n\n"
        f"🆔 Пользователь: `{target_id}`\n\n"
        f"Выберите что изменить:",
        reply_markup=keyboard
    )


@admin_router.callback_query(F.data.regexp(r'^admin_setcur_(\d+)_(vc|vt|bank)$'))
async def admin_set_currency_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    match = re.match(r'^admin_setcur_(\d+)_(vc|vt|bank)$', callback.data)
    target_id = int(match.group(1))
    currency = match.group(2)
    
    await state.update_data(target_id=target_id, currency=currency, action="set")
    await state.set_state(AdminStates.waiting_set_amount)
    
    currency_names = {"vc": "VineCoin (VC)", "vt": "VibeTon (VT)", "bank": "Банк"}
    
    await callback.message.edit_text(
        f"📝 **УСТАНОВКА БАЛАНСА**\n\n"
        f"🆔 Пользователь: `{target_id}`\n"
        f"💵 Изменяем: {currency_names[currency]}\n\n"
        f"Введите новое значение:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_back")]
        ])
    )


@admin_router.message(AdminStates.waiting_set_amount)
async def admin_set_amount_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    
    try:
        amount = float(message.text.replace(',', '.'))
        if amount < 0:
            raise ValueError
    except:
        await message.answer(f"{EMOJI['cross']} Введите корректную сумму!")
        return
    
    target_id = data['target_id']
    currency = data['currency']
    
    if currency == 'vc':
        await db.set_balance(target_id, coins=int(amount))
        result = f"💎 VC: {format_coins(int(amount))}"
    elif currency == 'vt':
        await db.set_balance(target_id, vibeton=amount)
        result = f"🔮 VT: {format_vibeton(amount)}"
    else:  # bank
        await db.set_bank_balance(target_id, int(amount))
        result = f"🏦 Банк: {format_coins(int(amount))}"
    
    await message.answer(
        f"✅ **Баланс установлен!**\n\n"
        f"🆔 Пользователь: `{target_id}`\n"
        f"{result}"
    )
    
    await state.clear()


@admin_router.message(F.text.lower().regexp(r'^аустановить\s+(\d+)\s+(vc|vt|bank|вк|вт|банк)\s+([\d.]+)$'))
async def admin_set_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    match = re.match(r'^аустановить\s+(\d+)\s+(vc|vt|bank|вк|вт|банк)\s+([\d.]+)$', message.text.lower())
    target_id = int(match.group(1))
    currency = match.group(2)
    amount = float(match.group(3))
    
    user = await db.get_user(target_id)
    if not user:
        await message.answer(f"{EMOJI['cross']} Пользователь не найден!")
        return
    
    if currency in ['vc', 'вк']:
        await db.set_balance(target_id, coins=int(amount))
        result = f"💎 VC: {format_coins(int(amount))}"
    elif currency in ['vt', 'вт']:
        await db.set_balance(target_id, vibeton=amount)
        result = f"🔮 VT: {format_vibeton(amount)}"
    else:
        await db.set_bank_balance(target_id, int(amount))
        result = f"🏦 Банк: {format_coins(int(amount))}"
    
    await message.answer(
        f"✅ **Установлено!**\n\n"
        f"👤 {user['first_name']} (`{target_id}`)\n"
        f"{result}"
    )


# ==================== ПРОМОКОДЫ ====================

@admin_router.callback_query(F.data == "admin_promos")
async def admin_promos_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    promos = await db.get_all_promos()
    
    text = f"🎁 **ПРОМОКОДЫ**\n{'═' * 30}\n\n"
    
    if promos:
        for promo in promos[:15]:
            status = "✅" if promo['is_active'] and promo['current_uses'] < promo['max_uses'] else "❌"
            text += (
                f"{status} `{promo['code']}`\n"
                f"   💎 {format_coins(promo['coins_reward'])} | 🔮 {format_vibeton(promo['vibeton_reward'])}\n"
                f"   👥 {promo['current_uses']}/{promo['max_uses']}\n\n"
            )
    else:
        text += "Промокодов пока нет\n"
    
    text += "\n📝 Команда создания:\n"
    text += "`асоздатьпромо <код> <vc> <vt> <макс>`"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_promos")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@admin_router.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        f"🎁 **СОЗДАНИЕ ПРОМОКОДА**\n\n"
        f"Введите код промокода (латиница, цифры):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_promos")]
        ])
    )
    
    await state.set_state(AdminStates.waiting_promo_code)


@admin_router.message(AdminStates.waiting_promo_code)
async def admin_promo_code_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    code = message.text.upper().strip()
    
    if not re.match(r'^[A-Z0-9]{3,20}$', code):
        await message.answer(f"{EMOJI['cross']} Код должен содержать только латиницу и цифры (3-20 символов)")
        return
    
    # Проверяем существование
    existing = await db.get_promo(code)
    if existing:
        await message.answer(f"{EMOJI['cross']} Такой промокод уже существует!")
        return
    
    await state.update_data(code=code)
    await state.set_state(AdminStates.waiting_promo_coins)
    
    await message.answer(
        f"🎁 **СОЗДАНИЕ ПРОМОКОДА**\n\n"
        f"📝 Код: `{code}`\n\n"
        f"Введите награду в VC (0 если не нужно):"
    )


@admin_router.message(AdminStates.waiting_promo_coins)
async def admin_promo_coins_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        coins = int(message.text)
        if coins < 0:
            raise ValueError
    except:
        await message.answer(f"{EMOJI['cross']} Введите корректное число!")
        return
    
    await state.update_data(coins=coins)
    await state.set_state(AdminStates.waiting_promo_vibeton)
    
    data = await state.get_data()
    
    await message.answer(
        f"🎁 **СОЗДАНИЕ ПРОМОКОДА**\n\n"
        f"📝 Код: `{data['code']}`\n"
        f"💎 VC: {format_coins(coins)}\n\n"
        f"Введите награду в VT (0 если не нужно):"
    )


@admin_router.message(AdminStates.waiting_promo_vibeton)
async def admin_promo_vt_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        vibeton = float(message.text.replace(',', '.'))
        if vibeton < 0:
            raise ValueError
    except:
        await message.answer(f"{EMOJI['cross']} Введите корректное число!")
        return
    
    await state.update_data(vibeton=vibeton)
    await state.set_state(AdminStates.waiting_promo_uses)
    
    data = await state.get_data()
    
    await message.answer(
        f"🎁 **СОЗДАНИЕ ПРОМОКОДА**\n\n"
        f"📝 Код: `{data['code']}`\n"
        f"💎 VC: {format_coins(data['coins'])}\n"
        f"🔮 VT: {format_vibeton(vibeton)}\n\n"
        f"Введите максимальное количество использований:"
    )


@admin_router.message(AdminStates.waiting_promo_uses)
async def admin_promo_uses_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        max_uses = int(message.text)
        if max_uses <= 0:
            raise ValueError
    except:
        await message.answer(f"{EMOJI['cross']} Введите корректное число!")
        return
    
    data = await state.get_data()
    
    await db.create_promo(data['code'], data['coins'], data['vibeton'], max_uses)
    
    await message.answer(
        f"✅ **ПРОМОКОД СОЗДАН!**\n\n"
        f"📝 Код: `{data['code']}`\n"
        f"💎 VC: {format_coins(data['coins'])}\n"
        f"🔮 VT: {format_vibeton(data['vibeton'])}\n"
        f"👥 Макс. использований: {max_uses}"
    )
    
    await state.clear()


@admin_router.message(F.text.lower().regexp(r'^асоздатьпромо\s+(\S+)\s+(\d+)\s+([\d.]+)\s+(\d+)$'))
async def admin_create_promo_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    match = re.match(r'^асоздатьпромо\s+(\S+)\s+(\d+)\s+([\d.]+)\s+(\d+)$', message.text.lower())
    code = match.group(1).upper()
    coins = int(match.group(2))
    vibeton = float(match.group(3))
    max_uses = int(match.group(4))
    
    existing = await db.get_promo(code)
    if existing:
        await message.answer(f"{EMOJI['cross']} Такой промокод уже существует!")
        return
    
    await db.create_promo(code, coins, vibeton, max_uses)
    
    await message.answer(
        f"✅ **Промокод создан!**\n\n"
        f"📝 Код: `{code}`\n"
        f"💎 VC: {format_coins(coins)}\n"
        f"🔮 VT: {format_vibeton(vibeton)}\n"
        f"👥 Макс: {max_uses}"
    )


@admin_router.message(F.text.lower().regexp(r'^аудалитьпромо\s+(\S+)$'))
async def admin_delete_promo_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    match = re.match(r'^аудалитьпромо\s+(\S+)$', message.text.lower())
    code = match.group(1).upper()
    
    await db.delete_promo(code)
    await message.answer(f"✅ Промокод `{code}` удален!")


# ==================== РАССЫЛКА ====================

@admin_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        f"📢 **РАССЫЛКА**\n\n"
        f"Введите текст сообщения для рассылки всем пользователям:\n\n"
        f"⚠️ Поддерживается Markdown форматирование",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_back")]
        ])
    )
    
    await state.set_state(AdminStates.waiting_broadcast_message)


@admin_router.message(AdminStates.waiting_broadcast_message)
async def admin_broadcast_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    text = message.text
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="admin_broadcast_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")
        ]
    ])
    
    await state.update_data(broadcast_text=text)
    
    await message.answer(
        f"📢 **ПРЕДПРОСМОТР РАССЫЛКИ**\n"
        f"{'═' * 30}\n\n"
        f"{text}\n\n"
        f"{'═' * 30}\n"
        f"Отправить всем пользователям?",
        reply_markup=keyboard
    )


@admin_router.callback_query(F.data == "admin_broadcast_confirm")
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    data = await state.get_data()
    text = data.get('broadcast_text')
    
    if not text:
        await callback.answer("Текст не найден!", show_alert=True)
        return
    
    await state.clear()
    
    # Получаем всех пользователей
    users = await db.get_all_users()
    
    await callback.message.edit_text(
        f"📢 **РАССЫЛКА**\n\n"
        f"⏳ Начинаю отправку...\n"
        f"👥 Получателей: {len(users)}"
    )
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            await callback.bot.send_message(user['user_id'], text)
            success += 1
        except Exception as e:
            failed += 1
    
    await callback.message.edit_text(
        f"📢 **РАССЫЛКА ЗАВЕРШЕНА**\n\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ])
    )


@admin_router.message(F.text.lower().regexp(r'^арассылка\s+(.+)$', flags=re.DOTALL))
async def admin_broadcast_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    match = re.match(r'^арассылка\s+(.+)$', message.text, flags=re.DOTALL)
    text = match.group(1)
    
    users = await db.get_all_users()
    
    msg = await message.answer(
        f"📢 Начинаю рассылку...\n"
        f"👥 Получателей: {len(users)}"
    )
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            await message.bot.send_message(user['user_id'], text)
            success += 1
        except:
            failed += 1
    
    await msg.edit_text(
        f"✅ **Рассылка завершена!**\n\n"
        f"📨 Успешно: {success}\n"
        f"❌ Ошибок: {failed}"
    )


# ==================== СБРОС ДАННЫХ ====================

@admin_router.callback_query(F.data.startswith("admin_reset_user_"))
async def admin_reset_user_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    target_id = int(callback.data.replace("admin_reset_user_", ""))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, сбросить", callback_data=f"admin_reset_confirm_{target_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")
        ]
    ])
    
    await callback.message.edit_text(
        f"🗑 **СБРОС ДАННЫХ ИГРОКА**\n\n"
        f"🆔 ID: `{target_id}`\n\n"
        f"⚠️ Это действие сбросит:\n"
        f"• Баланс VC и VT\n"
        f"• Банковский счёт\n"
        f"• Статистику игр\n"
        f"• Все видеокарты\n"
        f"• Ордера на рынке\n\n"
        f"**Вы уверены?**",
        reply_markup=keyboard
    )


@admin_router.callback_query(F.data.startswith("admin_reset_confirm_"))
async def admin_reset_confirm_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    target_id = int(callback.data.replace("admin_reset_confirm_", ""))
    
    await db.reset_user_data(target_id)
    
    await callback.message.edit_text(
        f"✅ **Данные игрока сброшены!**\n\n"
        f"🆔 ID: `{target_id}`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ])
    )


@admin_router.message(F.text.lower().regexp(r'^асброс\s+(\d+)$'))
async def admin_reset_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    match = re.match(r'^асброс\s+(\d+)$', message.text.lower())
    target_id = int(match.group(1))
    
    await db.reset_user_data(target_id)
    
    await message.answer(f"✅ Данные пользователя `{target_id}` сброшены!")


# ==================== УПРАВЛЕНИЕ РЫНКОМ ====================

@admin_router.callback_query(F.data == "admin_market")
async def admin_market_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    from market import get_current_price
    current_price = await get_current_price()
    orders = await db.get_market_orders()
    
    text = (
        f"💹 **УПРАВЛЕНИЕ РЫНКОМ**\n"
        f"{'═' * 30}\n\n"
        f"📊 Текущий курс: {format_coins(current_price)}/VT\n"
        f"📋 Активных ордеров: {len(orders)}\n\n"
        f"📝 Команды:\n"
        f"• `ацена <число>` - установить курс\n"
        f"• `аочиститьрынок` - удалить все ордера"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить курс случайно", callback_data="admin_market_random_price")],
        [InlineKeyboardButton(text="🗑 Очистить все ордера", callback_data="admin_market_clear")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@admin_router.callback_query(F.data == "admin_market_random_price")
async def admin_market_random_price(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    import random
    new_price = random.randint(1000, 15000)
    await db.update_market_price(new_price)
    
    await callback.answer(f"✅ Новый курс: {format_coins(new_price)}/VT", show_alert=True)
    
    # Обновляем сообщение
    from market import get_current_price
    orders = await db.get_market_orders()
    
    text = (
        f"💹 **УПРАВЛЕНИЕ РЫНКОМ**\n"
        f"{'═' * 30}\n\n"
        f"📊 Текущий курс: {format_coins(new_price)}/VT\n"
        f"📋 Активных ордеров: {len(orders)}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить курс случайно", callback_data="admin_market_random_price")],
        [InlineKeyboardButton(text="🗑 Очистить все ордера", callback_data="admin_market_clear")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@admin_router.callback_query(F.data == "admin_market_clear")
async def admin_market_clear(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await db.clear_all_market_orders()
    await callback.answer("✅ Все ордера удалены!", show_alert=True)


@admin_router.message(F.text.lower().regexp(r'^ацена\s+(\d+)$'))
async def admin_set_price_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    match = re.match(r'^ацена\s+(\d+)$', message.text.lower())
    price = int(match.group(1))
    
    await db.update_market_price(price)
    
    await message.answer(f"✅ Курс установлен: {format_coins(price)}/VT")


# ==================== ПОМОЩЬ ДЛЯ АДМИНОВ ====================

@admin_router.message(F.text.lower().in_(['апомощь', 'ahelp', 'админпомощь']))
async def admin_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    text = (
        f"🔐 **КОМАНДЫ АДМИНИСТРАТОРА**\n"
        f"{'═' * 30}\n\n"
        
        f"📊 **Общее:**\n"
        f"• `админ` - админ-панель\n"
        f"• `астатистика` - глобальная статистика\n\n"
        
        f"👤 **Пользователи:**\n"
        f"• `астат <id/@user>` - инфо о игроке\n"
        f"• `абан <id> [причина]` - забанить\n"
        f"• `аразбан <id>` - разбанить\n"
        f"• `асброс <id>` - сбросить данные\n\n"
        
        f"💰 **Экономика:**\n"
        f"• `авыдать <id> <сумма> [vt]` - выдать\n"
        f"• `аустановить <id> <vc/vt/bank> <сумма>` - установить\n\n"
        
        f"🎁 **Промокоды:**\n"
        f"• `асоздатьпромо <код> <vc> <vt> <макс>` - создать\n"
        f"• `аудалитьпромо <код>` - удалить\n\n"
        
        f"💹 **Рынок:**\n"
        f"• `ацена <число>` - установить курс VT\n"
        f"• `аочиститьрынок` - удалить все ордера\n\n"
        
        f"📢 **Рассылка:**\n"
        f"• `арассылка <текст>` - отправить всем"
    )
    
    await message.answer(text)
