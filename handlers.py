import random
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import GPU_CONFIG, JOBS_CONFIG
from utils import format_num, parse_amount, get_level, get_xp_for_next_level, maybe_give_xp

router = Router()


class MarketStates(StatesGroup):
    waiting_sell_amount = State()
    waiting_sell_price = State()


class BankStates(StatesGroup):
    waiting_deposit = State()
    waiting_withdraw = State()
    waiting_transfer_user = State()
    waiting_transfer_amount = State()


class ElectionStates(StatesGroup):
    waiting_bet = State()


# ==================== ПРОФИЛЬ ====================

@router.message(F.text.lower().in_(['я', 'б', 'проф', 'профиль', 'п', 'баланс']))
async def profile_handler(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
        user = await db.get_user(message.from_user.id)
    
    level = get_level(user['xp'])
    next_xp = get_xp_for_next_level(level)
    
    text = (
        f"👤 **{message.from_user.first_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 `{message.from_user.id}`\n\n"
        f"💎 **{format_num(user['coins'])}** VC\n"
        f"🔮 **{user['vibeton']:.2f}** VT\n"
        f"🏦 **{format_num(user['bank_balance'])}** VC\n\n"
        f"⭐ Уровень: **{level}** ({user['xp']}/{next_xp} XP)\n\n"
        f"🎮 Игр: **{user['total_games']}**\n"
        f"🏆 Побед: **{user['total_wins']}**\n"
        f"📈 Выиграл: **{format_num(user['total_earned'])}** VC\n"
        f"📉 Слил: **{format_num(user['total_lost'])}** VC"
    )
    
    president = await db.get_president()
    if president and president['user_id'] == message.from_user.id:
        taxes = await db.get_president_taxes_today(message.from_user.id)
        text += f"\n\n👑 **Ты президент!**\n💰 Налоги сегодня: **{format_num(taxes)}** VC"
    
    await message.answer(text)


# ==================== РАБОТА ====================

@router.message(F.text.lower().in_(['работа', 'работы', 'раб']))
async def jobs_list(message: Message):
    keyboard_rows = []
    for key, job in JOBS_CONFIG.items():
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{job['emoji']} {job['name']} ({format_num(job['min_salary'])}-{format_num(job['max_salary'])})",
                callback_data=f"work_{key}"
            )
        ])
    keyboard_rows.append([InlineKeyboardButton(text="❓ Что это?", callback_data="info_work")])
    
    await message.answer(
        "💼 **РАБОТА**\n━━━━━━━━━━━━━━━━━━━━\n\n🔽 Выбери работу:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    )


@router.callback_query(F.data.startswith('work_'))
async def work_callback(callback: CallbackQuery):
    job_key = callback.data.replace('work_', '')
    
    if job_key not in JOBS_CONFIG:
        await callback.answer("❌ Работа не найдена!", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    can_work = await db.can_work(callback.from_user.id)
    
    if not can_work:
        cooldown = await db.get_work_cooldown(callback.from_user.id)
        await callback.answer(f"⏰ Отдохни ещё {cooldown // 60}м {cooldown % 60}с", show_alert=True)
        return
    
    job = JOBS_CONFIG[job_key]
    salary = random.randint(job['min_salary'], job['max_salary'])
    
    await callback.message.edit_text(f"{job['emoji']} Работаю **{job['name']}**...")
    await asyncio.sleep(2)
    
    await db.update_coins(callback.from_user.id, salary)
    await db.set_work_time(callback.from_user.id)
    
    xp = maybe_give_xp()
    if xp > 0:
        await db.add_xp(callback.from_user.id, xp)
    
    await callback.message.edit_text(
        f"{job['emoji']} **{job['name']}**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Готово!\n💰 **+{format_num(salary)}** VC" + (f"\n⭐ +{xp} XP" if xp > 0 else "")
    )


@router.callback_query(F.data == "info_work")
async def info_work(callback: CallbackQuery):
    await callback.answer("💼 Работа — заработок VC. Кулдаун 30 минут.", show_alert=True)


# ==================== БАНК ====================

@router.message(F.text.lower().in_(['банк', 'bank']))
async def bank_handler(message: Message):
    user = await db.get_user(message.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Депозит", callback_data="bank_deposit"),
            InlineKeyboardButton(text="📤 Снять", callback_data="bank_withdraw"),
        ],
        [InlineKeyboardButton(text="💸 Перевод", callback_data="bank_transfer")],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_bank")]
    ])
    
    await message.answer(
        f"🏦 **БАНК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 На руках: **{format_num(user['coins'])}** VC\n"
        f"🏦 В банке: **{format_num(user['bank_balance'])}** VC",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "bank_deposit")
async def bank_deposit_start(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="10к", callback_data="dep_10000"),
            InlineKeyboardButton(text="100к", callback_data="dep_100000"),
            InlineKeyboardButton(text="1кк", callback_data="dep_1000000"),
        ],
        [InlineKeyboardButton(text="ВСЁ", callback_data=f"dep_{user['coins']}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]
    ])
    
    await callback.message.edit_text(
        f"📥 **ДЕПОЗИТ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Доступно: **{format_num(user['coins'])}** VC\n\n"
        f"Выбери сумму или введи свою:",
        reply_markup=keyboard
    )
    await state.set_state(BankStates.waiting_deposit)


@router.callback_query(F.data.startswith("dep_"))
async def bank_deposit_callback(callback: CallbackQuery, state: FSMContext):
    amount = int(callback.data.split("_")[1])
    
    success = await db.deposit_to_bank(callback.from_user.id, amount)
    await state.clear()
    
    if success:
        xp = maybe_give_xp()
        if xp > 0:
            await db.add_xp(callback.from_user.id, xp)
        await callback.message.edit_text(f"✅ **Депозит**\n\n🏦 +**{format_num(amount)}** VC в банк")
    else:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)


@router.message(BankStates.waiting_deposit)
async def bank_deposit_message(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(message.text, user['coins'])
    
    if amount <= 0:
        await message.answer("❌ Некорректная сумма!")
        return
    
    success = await db.deposit_to_bank(message.from_user.id, amount)
    await state.clear()
    
    if success:
        await message.answer(f"✅ 🏦 +**{format_num(amount)}** VC в банк")
    else:
        await message.answer("❌ Недостаточно средств!")


@router.callback_query(F.data == "bank_withdraw")
async def bank_withdraw_start(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="10к", callback_data="wth_10000"),
            InlineKeyboardButton(text="100к", callback_data="wth_100000"),
            InlineKeyboardButton(text="1кк", callback_data="wth_1000000"),
        ],
        [InlineKeyboardButton(text="ВСЁ", callback_data=f"wth_{user['bank_balance']}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]
    ])
    
    await callback.message.edit_text(
        f"📤 **СНЯТЬ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏦 В банке: **{format_num(user['bank_balance'])}** VC",
        reply_markup=keyboard
    )
    await state.set_state(BankStates.waiting_withdraw)


@router.callback_query(F.data.startswith("wth_"))
async def bank_withdraw_callback(callback: CallbackQuery, state: FSMContext):
    amount = int(callback.data.split("_")[1])
    
    success = await db.withdraw_from_bank(callback.from_user.id, amount)
    await state.clear()
    
    if success:
        await callback.message.edit_text(f"✅ **Снято**\n\n💰 +**{format_num(amount)}** VC")
    else:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)


@router.callback_query(F.data == "bank_transfer")
async def bank_transfer_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💸 **ПЕРЕВОД**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введи @username получателя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Отмена", callback_data="bank_back")]])
    )
    await state.set_state(BankStates.waiting_transfer_user)


@router.message(BankStates.waiting_transfer_user)
async def bank_transfer_user(message: Message, state: FSMContext):
    username = message.text.replace('@', '').strip()
    target = await db.get_user_by_username(username)
    
    if not target:
        await message.answer("❌ Пользователь не найден!")
        return
    if target['user_id'] == message.from_user.id:
        await message.answer("❌ Нельзя перевести себе!")
        return
    
    await state.update_data(target_id=target['user_id'], target_name=username)
    await state.set_state(BankStates.waiting_transfer_amount)
    
    user = await db.get_user(message.from_user.id)
    await message.answer(f"💸 **ПЕРЕВОД → @{username}**\n\n💰 Доступно: **{format_num(user['coins'])}** VC\n\nВведи сумму:")


@router.message(BankStates.waiting_transfer_amount)
async def bank_transfer_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(message.text, user['coins'])
    
    if amount <= 0:
        await message.answer("❌ Некорректная сумма!")
        return
    
    success = await db.transfer_coins(message.from_user.id, data['target_id'], amount)
    await state.clear()
    
    if success:
        xp = maybe_give_xp()
        if xp > 0:
            await db.add_xp(message.from_user.id, xp)
        await message.answer(f"✅ **Переведено**\n\n💸 **{format_num(amount)}** VC → @{data['target_name']}")
    else:
        await message.answer("❌ Недостаточно средств!")


@router.callback_query(F.data == "bank_back")
async def bank_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Депозит", callback_data="bank_deposit"),
            InlineKeyboardButton(text="📤 Снять", callback_data="bank_withdraw"),
        ],
        [InlineKeyboardButton(text="💸 Перевод", callback_data="bank_transfer")],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_bank")]
    ])
    
    await callback.message.edit_text(
        f"🏦 **БАНК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 На руках: **{format_num(user['coins'])}** VC\n"
        f"🏦 В банке: **{format_num(user['bank_balance'])}** VC",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "info_bank")
async def info_bank(callback: CallbackQuery):
    await callback.answer("🏦 Банк — храни деньги, переводи другим. Безопасно!", show_alert=True)
    # ==================== РЫНОК ====================

async def get_market_price():
    price_data = await db.get_market_price()
    if not price_data:
        price = random.randint(1000, 15000)
        await db.update_market_price(price)
        return price
    
    if datetime.utcnow() - price_data['updated_at'] > timedelta(hours=1):
        price = random.randint(1000, 15000)
        await db.update_market_price(price)
        return price
    
    return price_data['price']


def build_market_keyboard(orders):
    keyboard_rows = []

    if orders:
        for o in orders[:10]:
            name = o['username'] or o['first_name'] or 'Аноним'
            text = f"🟢 {name} | {o['amount']:.2f} VT | {format_num(o['price_per_unit'])}"
            keyboard_rows.append([
                InlineKeyboardButton(text=text, callback_data=f"mkt_view_{o['id']}")
            ])

    keyboard_rows.extend([
        [
            InlineKeyboardButton(text="🟢 Купить у бота", callback_data="mkt_buy_bot"),
            InlineKeyboardButton(text="🔴 Продать боту", callback_data="mkt_sell_bot"),
        ],
        [InlineKeyboardButton(text="🟡 Создать ордер", callback_data="mkt_create")],
        [InlineKeyboardButton(text="🔵 Мои ордера", callback_data="mkt_my")],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_market")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="mkt_refresh")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


@router.message(F.text.lower().in_(['рынок', 'маркет', 'market']))
async def market_handler(message: Message):
    price = await get_market_price()
    sell_orders = await db.get_market_orders('sell')

    text = (
        f"🛒 **РЫНОК VT**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 Бот покупает VT по: **{format_num(price)}** VC\n"
        f"⏰ Курс меняется каждый час\n\n"
        f"📦 Активных ордеров: **{len(sell_orders)}**"
    )

    await message.answer(text, reply_markup=build_market_keyboard(sell_orders))


@router.callback_query(F.data == "mkt_refresh")
async def market_refresh(callback: CallbackQuery):
    price = await get_market_price()
    sell_orders = await db.get_market_orders('sell')

    text = (
        f"🛒 **РЫНОК VT**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 Бот покупает VT по: **{format_num(price)}** VC\n"
        f"⏰ Курс меняется каждый час\n\n"
        f"📦 Активных ордеров: **{len(sell_orders)}**"
    )

    await callback.message.edit_text(text, reply_markup=build_market_keyboard(sell_orders))
    await callback.answer("🔄 Обновлено!")


@router.callback_query(F.data == "info_market")
async def info_market(callback: CallbackQuery):
    await callback.answer(
        "🛒 Рынок — место покупки и продажи VT.\n"
        "🤖 Бот всегда покупает VT по текущему курсу.\n"
        "👤 Игроки могут создавать свои ордера на продажу.",
        show_alert=True
    )


@router.callback_query(F.data.startswith("mkt_view_"))
async def market_view_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order_by_id(order_id)

    if not order or not order['is_active']:
        await callback.answer("❌ Ордер не найден!", show_alert=True)
        return

    seller = await db.get_user(order['user_id'])
    name = seller['username'] or seller['first_name'] or 'Аноним'
    total = int(order['amount'] * order['price_per_unit'])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🟢 Купить всё ({order['amount']:.2f} VT)", callback_data=f"mkt_buyall_{order_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="mkt_refresh")]
    ])

    await callback.message.edit_text(
        f"📋 **ОРДЕР**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Продавец: **{name}**\n"
        f"🔮 Кол-во: **{order['amount']:.2f}** VT\n"
        f"💰 Цена: **{format_num(order['price_per_unit'])}** VC/VT\n"
        f"💵 Итого: **{format_num(total)}** VC",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("mkt_buyall_"))
async def market_buy_all(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    success, result = await db.buy_from_market(callback.from_user.id, order_id)

    if success:
        total = int(result['amount'] * result['price_per_unit'])
        xp = maybe_give_xp()
        if xp > 0:
            await db.add_xp(callback.from_user.id, xp)

        await callback.message.edit_text(
            f"✅ **ПОКУПКА УСПЕШНА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔮 Куплено: **{result['amount']:.2f}** VT\n"
            f"💰 Потрачено: **{format_num(total)}** VC"
            + (f"\n⭐ +{xp} XP" if xp > 0 else "")
        )
    else:
        errors = {
            "not_found": "❌ Ордер не найден!",
            "no_money": "❌ Недостаточно VC!"
        }
        await callback.answer(errors.get(result, "❌ Ошибка!"), show_alert=True)


@router.callback_query(F.data == "mkt_buy_bot")
async def market_buy_bot(callback: CallbackQuery):
    price = await get_market_price()
    user = await db.get_user(callback.from_user.id)
    max_buy = user['coins'] / price if price > 0 else 0

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 VT", callback_data="botbuy_1"),
            InlineKeyboardButton(text="5 VT", callback_data="botbuy_5"),
            InlineKeyboardButton(text="10 VT", callback_data="botbuy_10"),
        ],
        [InlineKeyboardButton(text=f"MAX ({max_buy:.2f})", callback_data="botbuy_max")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="mkt_refresh")]
    ])

    await callback.message.edit_text(
        f"🟢 **КУПИТЬ У БОТА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Курс: **{format_num(price)}** VC/VT\n"
        f"💰 Баланс: **{format_num(user['coins'])}** VC\n"
        f"🔮 Макс можно купить: **{max_buy:.2f}** VT",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("botbuy_"))
async def bot_buy(callback: CallbackQuery):
    amount_str = callback.data.split("_")[1]
    price = await get_market_price()
    user = await db.get_user(callback.from_user.id)

    amount = user['coins'] / price if amount_str == "max" else float(amount_str)
    cost = int(amount * price)

    if user['coins'] < cost:
        await callback.answer("❌ Нет денег!", show_alert=True)
        return

    await db.update_coins(callback.from_user.id, -cost)
    await db.update_vibeton(callback.from_user.id, amount)

    xp = maybe_give_xp()
    if xp > 0:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text(
        f"✅ **ПОКУПКА У БОТА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔮 Куплено: **{amount:.2f}** VT\n"
        f"💰 Потрачено: **{format_num(cost)}** VC"
        + (f"\n⭐ +{xp} XP" if xp > 0 else "")
    )


@router.callback_query(F.data == "mkt_sell_bot")
async def market_sell_bot(callback: CallbackQuery):
    price = await get_market_price()
    user = await db.get_user(callback.from_user.id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 VT", callback_data="botsell_1"),
            InlineKeyboardButton(text="5 VT", callback_data="botsell_5"),
            InlineKeyboardButton(text="10 VT", callback_data="botsell_10"),
        ],
        [InlineKeyboardButton(text=f"ВСЁ ({user['vibeton']:.2f})", callback_data="botsell_all")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="mkt_refresh")]
    ])

    await callback.message.edit_text(
        f"🔴 **ПРОДАТЬ БОТУ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Курс: **{format_num(price)}** VC/VT\n"
        f"🔮 Баланс: **{user['vibeton']:.2f}** VT",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("botsell_"))
async def bot_sell(callback: CallbackQuery):
    amount_str = callback.data.split("_")[1]
    price = await get_market_price()
    user = await db.get_user(callback.from_user.id)

    amount = user['vibeton'] if amount_str == "all" else float(amount_str)

    if user['vibeton'] < amount:
        await callback.answer("❌ Нет VT!", show_alert=True)
        return

    earn = int(amount * price)
    await db.update_vibeton(callback.from_user.id, -amount)
    await db.update_coins(callback.from_user.id, earn)

    xp = maybe_give_xp()
    if xp > 0:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text(
        f"✅ **ПРОДАЖА БОТУ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔮 Продано: **{amount:.2f}** VT\n"
        f"💰 Получено: **{format_num(earn)}** VC"
        + (f"\n⭐ +{xp} XP" if xp > 0 else "")
    )


@router.callback_query(F.data == "mkt_create")
async def market_create(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"🟡 **СОЗДАТЬ ОРДЕР**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔮 Твой баланс: **{user['vibeton']:.2f}** VT\n\n"
        f"Введи количество VT для продажи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="mkt_refresh")]
        ])
    )
    await state.set_state(MarketStates.waiting_sell_amount)


@router.message(MarketStates.waiting_sell_amount)
async def market_sell_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
    except:
        await message.answer("❌ Введи число!")
        return

    user = await db.get_user(message.from_user.id)
    if amount <= 0 or amount > user['vibeton']:
        await message.answer(f"❌ У тебя **{user['vibeton']:.2f}** VT")
        return

    await state.update_data(sell_amount=amount)
    await state.set_state(MarketStates.waiting_sell_price)

    price = await get_market_price()
    await message.answer(
        f"🟡 **СОЗДАТЬ ОРДЕР**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔮 Кол-во: **{amount:.2f}** VT\n"
        f"🤖 Курс бота: **{format_num(price)}** VC\n\n"
        f"Введи цену за 1 VT:"
    )


@router.message(MarketStates.waiting_sell_price)
async def market_sell_price(message: Message, state: FSMContext):
    price = parse_amount(message.text, 10**18)
    if price <= 0:
        await message.answer("❌ Введи корректную цену!")
        return

    data = await state.get_data()
    amount = data['sell_amount']

    success = await db.create_market_order(message.from_user.id, 'sell', amount, price)
    await state.clear()

    if success:
        xp = maybe_give_xp()
        if xp > 0:
            await db.add_xp(message.from_user.id, xp)

        await message.answer(
            f"✅ **ОРДЕР СОЗДАН**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔮 **{amount:.2f}** VT\n"
            f"💰 **{format_num(price)}** VC/VT"
            + (f"\n⭐ +{xp} XP" if xp > 0 else "")
        )
    else:
        await message.answer("❌ Недостаточно VT!")


@router.callback_query(F.data == "mkt_my")
async def market_my(callback: CallbackQuery):
    orders = await db.get_user_market_orders(callback.from_user.id)
    text = "🔵 **МОИ ОРДЕРА**\n━━━━━━━━━━━━━━━━━━━━\n\n"

    if orders:
        for o in orders:
            text += f"🔮 **{o['amount']:.2f}** VT по **{format_num(o['price_per_unit'])}** VC\n"
    else:
        text += "❌ У тебя нет активных ордеров"

    keyboard_rows = [
        [InlineKeyboardButton(text=f"❌ Отменить {o['amount']:.2f} VT", callback_data=f"mkt_cancel_{o['id']}")]
        for o in orders
    ]
    keyboard_rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="mkt_refresh")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows))


@router.callback_query(F.data.startswith("mkt_cancel_"))
async def market_cancel(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    success = await db.cancel_market_order(callback.from_user.id, order_id)

    if success:
        await callback.answer("✅ Ордер отменён!", show_alert=True)
        await market_my(callback)
    else:
        await callback.answer("❌ Ошибка!", show_alert=True)
        # ==================== ТОП ====================

@router.message(F.text.lower().in_(['топ', 'top', 'рейтинг']))
async def top_handler(message: Message):
    top_coins = await db.get_top_coins(10)
    top_vt = await db.get_top_vibeton(10)

    text = "🏆 **ТОПЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "💎 **По VC:**\n"
    medals = ['🥇', '🥈', '🥉']

    for i, user in enumerate(top_coins):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = user['first_name'] or user['username'] or 'Аноним'
        text += f"{medal} {name}: **{format_num(user['coins'])}**\n"

    text += "\n🔮 **По VT:**\n"
    for i, user in enumerate(top_vt):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = user['first_name'] or user['username'] or 'Аноним'
        text += f"{medal} {name}: **{user['vibeton']:.2f}**\n"

    await message.answer(text)


# ==================== ПРОМО ====================

@router.message(F.text.lower().startswith('промо'))
async def promo_handler(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("🎁 Использование: `промо КОД`")
        return

    code = parts[1].upper()
    success, result = await db.use_promo(message.from_user.id, code)

    if success:
        rewards = []
        if result['coins_reward'] > 0:
            rewards.append(f"💎 {format_num(result['coins_reward'])} VC")
        if result['vibeton_reward'] > 0:
            rewards.append(f"🔮 {result['vibeton_reward']:.2f} VT")

        xp = maybe_give_xp()
        if xp > 0:
            await db.add_xp(message.from_user.id, xp)

        await message.answer(
            f"🎁 **ПРОМОКОД АКТИВИРОВАН**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{' | '.join(rewards)}" + (f"\n⭐ +{xp} XP" if xp > 0 else "")
        )
    else:
        errors = {
            "not_found": "❌ Промокод не найден!",
            "expired": "❌ Промокод закончился!",
            "already_used": "❌ Уже использован!"
        }
        await message.answer(errors.get(result, "❌ Ошибка!"))


# ==================== ПОМОЩЬ ====================

@router.message(CommandStart())
@router.message(F.text.lower().in_(['помощь', 'help', 'команды', 'хелп', 'start']))
async def help_handler(message: Message):
    await db.create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", callback_data="help_games")],
        [InlineKeyboardButton(text="💼 Системы", callback_data="help_systems")],
        [InlineKeyboardButton(text="👑 Президент", callback_data="help_president")]
    ])

    await message.answer(
        "🎮 **VIBEBOT**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Добро пожаловать!\n"
        "Выбери раздел помощи:",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "help_games")
async def help_games(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎮 **ИГРЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "💣 `мины 100к`\n"
        "💎 `алмазы 100к`\n"
        "🎡 `рулетка 100к`\n"
        "📈 `краш 100к 2.5`\n"
        "🎲 `кости 100к`\n"
        "⚽ `футбол 100к`\n"
        "🏀 `баскетбол 100к`\n"
        "🎳 `боулинг 100к`\n"
        "🎯 `дартс 100к`\n"
        "🎰 `слоты 100к`\n"
        "🃏 `бд 100к`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="help_back")]
        ])
    )


@router.callback_query(F.data == "help_systems")
async def help_systems(callback: CallbackQuery):
    await callback.message.edit_text(
        "💼 **СИСТЕМЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 `я` — профиль\n"
        "💼 `работа` — заработок\n"
        "⛏️ `ферма` — добыча VT\n"
        "🛒 `рынок` — торговля VT\n"
        "🏦 `банк` — депозит и переводы\n"
        "🏆 `топ` — рейтинги\n"
        "🎁 `промо КОД` — промокод\n\n"
        "⭐ За действия иногда даётся XP\n"
        "📈 25% шанс получить 1-2 XP",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="help_back")]
        ])
    )


@router.callback_query(F.data == "help_president")
async def help_president_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "👑 **ПРЕЗИДЕНТ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "• Налог 0.01% от операций\n"
        "• Ставки: 00:10 - 23:59 МСК\n"
        "• Итоги: 00:07 МСК\n"
        "• Победитель — случайный среди участников\n"
        "• Проигравшим 50% возврат\n"
        "• Президент не участвует в своих выборах\n\n"
        "Команда: `президент`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="help_back")]
        ])
    )


@router.callback_query(F.data == "help_back")
async def help_back(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", callback_data="help_games")],
        [InlineKeyboardButton(text="💼 Системы", callback_data="help_systems")],
        [InlineKeyboardButton(text="👑 Президент", callback_data="help_president")]
    ])

    await callback.message.edit_text(
        "🎮 **VIBEBOT**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Добро пожаловать!\n"
        "Выбери раздел помощи:",
        reply_markup=keyboard
    )
