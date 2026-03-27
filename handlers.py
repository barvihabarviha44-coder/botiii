import random
from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import GPU_CONFIG, JOBS_CONFIG
from utils import format_num, parse_amount, get_level, get_xp_for_next_level, maybe_give_xp

router = Router()
MSK = timezone(timedelta(hours=3))


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


# ==================== HELP TEXTS ====================

SYSTEM_INFOS = {
    "work": "💼 Работа — способ зарабатывать VC. У каждой работы есть минимальный уровень. После работы кулдаун 30 минут.",
    "bank": "🏦 Банк — хранит твои VC. Можно класть, снимать и переводить другим игрокам.",
    "farm": "⛏️ Ферма — добывает VT каждый час. Покупай видеокарты и собирай добычу.",
    "market": "🛒 Рынок — покупай и продавай VT. Бот всегда покупает VT по текущему курсу. Игроки могут выставлять свои ордера.",
    "president": "👑 Президент получает 0.01% от всех операций. Ставки принимаются с 00:10 до 23:59 МСК. Итоги в 00:07 МСК. Победитель выбирается случайно по весу ставок. Проигравшим возвращается 50%.",
}


# ==================== PROFILE ====================

@router.message(F.text.lower().in_(['я', 'б', 'проф', 'профиль', 'п', 'баланс']))
async def profile_handler(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
        user = await db.get_user(message.from_user.id)

    level = get_level(user["xp"])
    next_xp = get_xp_for_next_level(level)

    text = (
        f"👤 **{message.from_user.first_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 `{message.from_user.id}`\n\n"
        f"💎 **{format_num(user['coins'])}** VC\n"
        f"🔮 **{user['vibeton']:.2f}** VT\n"
        f"🏦 **{format_num(user['bank_balance'])}** VC\n\n"
        f"⭐ Уровень: **{level}**\n"
        f"📚 XP: **{user['xp']} / {next_xp}**\n\n"
        f"🎮 Игр: **{user['total_games']}**\n"
        f"🏆 Побед: **{user['total_wins']}**\n"
        f"📈 Выиграл: **{format_num(user['total_earned'])}** VC\n"
        f"📉 Слил: **{format_num(user['total_lost'])}** VC"
    )

    president = await db.get_president()
    if president and president["user_id"] == message.from_user.id:
        taxes = await db.get_president_taxes_today(message.from_user.id)
        text += f"\n\n👑 **Ты президент**\n💰 Налогов сегодня: **{format_num(taxes)}** VC"

    await message.answer(text)


# ==================== WORK ====================

@router.message(F.text.lower().in_(['работа', 'работы', 'раб']))
async def jobs_list(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
        user = await db.get_user(message.from_user.id)

    lvl = get_level(user["xp"])

    rows = []
    for key, job in JOBS_CONFIG.items():
        lock = "🔓" if lvl >= job["level"] else "🔒"
        rows.append([
            InlineKeyboardButton(
                text=f"{lock} {job['emoji']} {job['name']} | lvl {job['level']}",
                callback_data=f"work_{key}"
            )
        ])

    rows.append([InlineKeyboardButton(text="❓ Что это?", callback_data="sysinfo_work")])

    await message.answer(
        f"💼 **РАБОТЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⭐ Твой уровень: **{lvl}**\n\n"
        f"Выбери работу:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@router.callback_query(F.data.startswith("work_"))
async def work_callback(callback: CallbackQuery):
    job_key = callback.data.replace("work_", "")
    if job_key not in JOBS_CONFIG:
        await callback.answer("❌ Работа не найдена!", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    if not user:
        return

    lvl = get_level(user["xp"])
    job = JOBS_CONFIG[job_key]

    if lvl < job["level"]:
        await callback.answer(f"❌ Нужен {job['level']} уровень!", show_alert=True)
        return

    can_work = await db.can_work(callback.from_user.id)
    if not can_work:
        cd = await db.get_work_cooldown(callback.from_user.id)
        await callback.answer(f"⏰ Отдохни ещё {cd // 60}м {cd % 60}с", show_alert=True)
        return

    salary = random.randint(job["min_salary"], job["max_salary"])

    await callback.message.edit_text(
        f"{job['emoji']} **{job['name']}**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏳ Работаем..."
    )

    await db.set_work_time(callback.from_user.id)
    await db.update_coins(callback.from_user.id, salary)

    xp = maybe_give_xp()
    if xp > 0:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text(
        f"{job['emoji']} **{job['name']}**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Работа завершена!\n"
        f"💰 **+{format_num(salary)}** VC"
        + (f"\n⭐ +{xp} XP" if xp > 0 else "")
    )


@router.callback_query(F.data == "sysinfo_work")
async def sysinfo_work(callback: CallbackQuery):
    await callback.answer(SYSTEM_INFOS["work"], show_alert=True)


# ==================== BANK ====================

@router.message(F.text.lower().in_(['банк', 'bank']))
async def bank_handler(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        return

    kb = [
        [
            InlineKeyboardButton(text="🟢 Депозит", callback_data="bank_deposit"),
            InlineKeyboardButton(text="🟡 Снять", callback_data="bank_withdraw"),
        ],
        [InlineKeyboardButton(text="🔵 Перевод", callback_data="bank_transfer")],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="sysinfo_bank")]
    ]

    await message.answer(
        f"🏦 **БАНК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 На руках: **{format_num(user['coins'])}** VC\n"
        f"🏦 В банке: **{format_num(user['bank_balance'])}** VC",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@router.callback_query(F.data == "sysinfo_bank")
async def sysinfo_bank(callback: CallbackQuery):
    await callback.answer(SYSTEM_INFOS["bank"], show_alert=True)


@router.callback_query(F.data == "bank_deposit")
async def bank_deposit_start(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)

    kb = [
        [
            InlineKeyboardButton(text="10к", callback_data="dep_10000"),
            InlineKeyboardButton(text="100к", callback_data="dep_100000"),
            InlineKeyboardButton(text="1кк", callback_data="dep_1000000"),
        ],
        [InlineKeyboardButton(text="ВСЁ", callback_data=f"dep_{user['coins']}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]
    ]

    await callback.message.edit_text(
        f"🟢 **ДЕПОЗИТ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Доступно: **{format_num(user['coins'])}** VC\n\n"
        f"Выбери сумму или отправь сообщением:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.set_state(BankStates.waiting_deposit)


@router.callback_query(F.data.startswith("dep_"))
async def bank_deposit_callback(callback: CallbackQuery, state: FSMContext):
    amount = int(callback.data.split("_")[1])
    success = await db.deposit_to_bank(callback.from_user.id, amount)
    await state.clear()

    if success:
        xp = maybe_give_xp()
        if xp:
            await db.add_xp(callback.from_user.id, xp)
        await callback.message.edit_text(
            f"✅ **ДЕПОЗИТ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏦 **+{format_num(amount)}** VC в банк"
            + (f"\n⭐ +{xp} XP" if xp else "")
        )
    else:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)


@router.message(BankStates.waiting_deposit)
async def bank_deposit_message(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(message.text, user["coins"])

    if amount <= 0:
        await message.answer("❌ Некорректная сумма!")
        return

    success = await db.deposit_to_bank(message.from_user.id, amount)
    await state.clear()

    if success:
        xp = maybe_give_xp()
        if xp:
            await db.add_xp(message.from_user.id, xp)
        await message.answer(
            f"✅ **ДЕПОЗИТ**\n\n🏦 **+{format_num(amount)}** VC"
            + (f"\n⭐ +{xp} XP" if xp else "")
        )
    else:
        await message.answer("❌ Недостаточно средств!")


@router.callback_query(F.data == "bank_withdraw")
async def bank_withdraw_start(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)

    kb = [
        [
            InlineKeyboardButton(text="10к", callback_data="wth_10000"),
            InlineKeyboardButton(text="100к", callback_data="wth_100000"),
            InlineKeyboardButton(text="1кк", callback_data="wth_1000000"),
        ],
        [InlineKeyboardButton(text="ВСЁ", callback_data=f"wth_{user['bank_balance']}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]
    ]

    await callback.message.edit_text(
        f"🟡 **СНЯТИЕ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏦 В банке: **{format_num(user['bank_balance'])}** VC",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.set_state(BankStates.waiting_withdraw)


@router.callback_query(F.data.startswith("wth_"))
async def bank_withdraw_callback(callback: CallbackQuery, state: FSMContext):
    amount = int(callback.data.split("_")[1])
    success = await db.withdraw_from_bank(callback.from_user.id, amount)
    await state.clear()

    if success:
        xp = maybe_give_xp()
        if xp:
            await db.add_xp(callback.from_user.id, xp)
        await callback.message.edit_text(
            f"✅ **СНЯТИЕ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 **+{format_num(amount)}** VC"
            + (f"\n⭐ +{xp} XP" if xp else "")
        )
    else:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)


@router.message(BankStates.waiting_withdraw)
async def bank_withdraw_message(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(message.text, user["bank_balance"])

    if amount <= 0:
        await message.answer("❌ Некорректная сумма!")
        return

    success = await db.withdraw_from_bank(message.from_user.id, amount)
    await state.clear()

    if success:
        xp = maybe_give_xp()
        if xp:
            await db.add_xp(message.from_user.id, xp)
        await message.answer(
            f"✅ **СНЯТИЕ**\n\n💰 **+{format_num(amount)}** VC"
            + (f"\n⭐ +{xp} XP" if xp else "")
        )
    else:
        await message.answer("❌ Недостаточно средств!")


@router.callback_query(F.data == "bank_transfer")
async def bank_transfer_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔵 **ПЕРЕВОД**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введи `@username` получателя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="bank_back")]
        ])
    )
    await state.set_state(BankStates.waiting_transfer_user)


@router.message(BankStates.waiting_transfer_user)
async def bank_transfer_user(message: Message, state: FSMContext):
    username = message.text.replace("@", "").strip()
    target = await db.get_user_by_username(username)

    if not target:
        await message.answer("❌ Пользователь не найден!")
        return
    if target["user_id"] == message.from_user.id:
        await message.answer("❌ Нельзя перевести себе!")
        return

    await state.update_data(target_id=target["user_id"], target_username=username)
    await state.set_state(BankStates.waiting_transfer_amount)

    user = await db.get_user(message.from_user.id)
    await message.answer(
        f"🔵 **ПЕРЕВОД → @{username}**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Доступно: **{format_num(user['coins'])}** VC\n\n"
        f"Введи сумму:"
    )


@router.message(BankStates.waiting_transfer_amount)
async def bank_transfer_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(message.text, user["coins"])

    if amount <= 0:
        await message.answer("❌ Некорректная сумма!")
        return

    success = await db.transfer_coins(message.from_user.id, data["target_id"], amount)
    await state.clear()

    if success:
        xp = maybe_give_xp()
        if xp:
            await db.add_xp(message.from_user.id, xp)
        await message.answer(
            f"✅ **ПЕРЕВОД**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💸 **{format_num(amount)}** VC → @{data['target_username']}"
            + (f"\n⭐ +{xp} XP" if xp else "")
        )
    else:
        await message.answer("❌ Недостаточно средств!")


@router.callback_query(F.data == "bank_back")
async def bank_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(callback.from_user.id)

    kb = [
        [
            InlineKeyboardButton(text="🟢 Депозит", callback_data="bank_deposit"),
            InlineKeyboardButton(text="🟡 Снять", callback_data="bank_withdraw"),
        ],
        [InlineKeyboardButton(text="🔵 Перевод", callback_data="bank_transfer")],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="sysinfo_bank")]
    ]

    await callback.message.edit_text(
        f"🏦 **БАНК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 На руках: **{format_num(user['coins'])}** VC\n"
        f"🏦 В банке: **{format_num(user['bank_balance'])}** VC",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    # ==================== MARKET ====================

async def get_market_price():
    price_data = await db.get_market_price()
    if not price_data:
        price = random.randint(1000, 15000)
        await db.update_market_price(price)
        return price

    if datetime.utcnow() - price_data["updated_at"] > timedelta(hours=1):
        price = random.randint(1000, 15000)
        await db.update_market_price(price)
        return price

    return price_data["price"]


def market_keyboard(orders):
    rows = []

    if orders:
        for o in orders[:10]:
            name = o["username"] or o["first_name"] or "Аноним"
            rows.append([
                InlineKeyboardButton(
                    text=f"🟢 {name} | {o['amount']:.2f} VT | {format_num(o['price_per_unit'])}",
                    callback_data=f"mkt_view_{o['id']}"
                )
            ])

    rows.extend([
        [
            InlineKeyboardButton(text="🟢 Купить у бота", callback_data="mkt_buy_bot"),
            InlineKeyboardButton(text="🔴 Продать боту", callback_data="mkt_sell_bot"),
        ],
        [InlineKeyboardButton(text="🟡 Создать ордер", callback_data="mkt_create")],
        [InlineKeyboardButton(text="🔵 Мои ордера", callback_data="mkt_my")],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="sysinfo_market")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="mkt_refresh")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text.lower().in_(['рынок', 'маркет', 'market']))
async def market_handler(message: Message):
    price = await get_market_price()
    orders = await db.get_market_orders("sell")

    await message.answer(
        f"🛒 **РЫНОК VT**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 Бот покупает VT по: **{format_num(price)}** VC\n"
        f"📦 Ордеров на продажу: **{len(orders)}**\n"
        f"⏰ Курс меняется каждый час",
        reply_markup=market_keyboard(orders)
    )


@router.callback_query(F.data == "sysinfo_market")
async def sysinfo_market(callback: CallbackQuery):
    await callback.answer(SYSTEM_INFOS["market"], show_alert=True)


@router.callback_query(F.data == "mkt_refresh")
async def market_refresh(callback: CallbackQuery):
    price = await get_market_price()
    orders = await db.get_market_orders("sell")

    await callback.message.edit_text(
        f"🛒 **РЫНОК VT**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 Бот покупает VT по: **{format_num(price)}** VC\n"
        f"📦 Ордеров на продажу: **{len(orders)}**\n"
        f"⏰ Курс меняется каждый час",
        reply_markup=market_keyboard(orders)
    )
    await callback.answer("🔄 Обновлено!")


@router.callback_query(F.data.startswith("mkt_view_"))
async def market_view(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order_by_id(order_id)
    if not order or not order["is_active"]:
        await callback.answer("❌ Ордер не найден!", show_alert=True)
        return

    seller = await db.get_user(order["user_id"])
    name = seller["username"] or seller["first_name"] or "Аноним"
    total = int(order["amount"] * order["price_per_unit"])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🟢 Купить всё ({order['amount']:.2f} VT)", callback_data=f"mkt_buyall_{order_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="mkt_refresh")]
    ])

    await callback.message.edit_text(
        f"📋 **ОРДЕР**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Продавец: **{name}**\n"
        f"🔮 Кол-во: **{order['amount']:.2f}** VT\n"
        f"💰 Цена: **{format_num(order['price_per_unit'])}** VC/VT\n"
        f"💵 Итого: **{format_num(total)}** VC",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("mkt_buyall_"))
async def market_buy_all(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    success, result = await db.buy_from_market(callback.from_user.id, order_id)

    if success:
        total = int(result["amount"] * result["price_per_unit"])
        xp = maybe_give_xp()
        if xp:
            await db.add_xp(callback.from_user.id, xp)

        await callback.message.edit_text(
            f"✅ **ПОКУПКА УСПЕШНА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔮 Куплено: **{result['amount']:.2f}** VT\n"
            f"💰 Потрачено: **{format_num(total)}** VC"
            + (f"\n⭐ +{xp} XP" if xp else "")
        )
    else:
        await callback.answer("❌ Ошибка покупки!", show_alert=True)


@router.callback_query(F.data == "mkt_buy_bot")
async def market_buy_bot(callback: CallbackQuery):
    price = await get_market_price()
    user = await db.get_user(callback.from_user.id)
    max_buy = user["coins"] / price if price > 0 else 0

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 VT", callback_data="mbuy_1"),
            InlineKeyboardButton(text="5 VT", callback_data="mbuy_5"),
            InlineKeyboardButton(text="10 VT", callback_data="mbuy_10"),
        ],
        [InlineKeyboardButton(text=f"MAX ({max_buy:.2f})", callback_data="mbuy_max")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="mkt_refresh")]
    ])

    await callback.message.edit_text(
        f"🟢 **КУПИТЬ У БОТА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Курс: **{format_num(price)}** VC/VT\n"
        f"💰 Баланс: **{format_num(user['coins'])}** VC\n"
        f"🔮 Макс: **{max_buy:.2f}** VT",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("mbuy_"))
async def market_buy_bot_do(callback: CallbackQuery):
    amount_str = callback.data.split("_")[1]
    price = await get_market_price()
    user = await db.get_user(callback.from_user.id)

    amount = user["coins"] / price if amount_str == "max" else float(amount_str)
    cost = int(amount * price)

    if user["coins"] < cost or amount <= 0:
        await callback.answer("❌ Недостаточно VC!", show_alert=True)
        return

    await db.update_coins(callback.from_user.id, -cost)
    await db.update_vibeton(callback.from_user.id, amount)

    xp = maybe_give_xp()
    if xp:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text(
        f"✅ **ПОКУПКА У БОТА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔮 Куплено: **{amount:.2f}** VT\n"
        f"💰 Потрачено: **{format_num(cost)}** VC"
        + (f"\n⭐ +{xp} XP" if xp else "")
    )


@router.callback_query(F.data == "mkt_sell_bot")
async def market_sell_bot(callback: CallbackQuery):
    price = await get_market_price()
    user = await db.get_user(callback.from_user.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 VT", callback_data="msell_1"),
            InlineKeyboardButton(text="5 VT", callback_data="msell_5"),
            InlineKeyboardButton(text="10 VT", callback_data="msell_10"),
        ],
        [InlineKeyboardButton(text=f"ВСЁ ({user['vibeton']:.2f})", callback_data="msell_all")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="mkt_refresh")]
    ])

    await callback.message.edit_text(
        f"🔴 **ПРОДАТЬ БОТУ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Курс: **{format_num(price)}** VC/VT\n"
        f"🔮 Баланс: **{user['vibeton']:.2f}** VT",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("msell_"))
async def market_sell_bot_do(callback: CallbackQuery):
    amount_str = callback.data.split("_")[1]
    price = await get_market_price()
    user = await db.get_user(callback.from_user.id)

    amount = user["vibeton"] if amount_str == "all" else float(amount_str)

    if amount <= 0 or user["vibeton"] < amount:
        await callback.answer("❌ Недостаточно VT!", show_alert=True)
        return

    earn = int(amount * price)
    await db.update_vibeton(callback.from_user.id, -amount)
    await db.update_coins(callback.from_user.id, earn)

    xp = maybe_give_xp()
    if xp:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text(
        f"✅ **ПРОДАЖА БОТУ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔮 Продано: **{amount:.2f}** VT\n"
        f"💰 Получено: **{format_num(earn)}** VC"
        + (f"\n⭐ +{xp} XP" if xp else "")
    )


@router.callback_query(F.data == "mkt_create")
async def market_create(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"🟡 **СОЗДАТЬ ОРДЕР**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔮 Баланс: **{user['vibeton']:.2f}** VT\n\n"
        f"Введи количество VT для продажи:"
    )
    await state.set_state(MarketStates.waiting_sell_amount)


@router.message(MarketStates.waiting_sell_amount)
async def market_sell_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except:
        await message.answer("❌ Введи число!")
        return

    user = await db.get_user(message.from_user.id)
    if amount <= 0 or amount > user["vibeton"]:
        await message.answer(f"❌ У тебя только **{user['vibeton']:.2f}** VT")
        return

    await state.update_data(sell_amount=amount)
    await state.set_state(MarketStates.waiting_sell_price)

    bot_price = await get_market_price()
    await message.answer(
        f"🟡 **СОЗДАТЬ ОРДЕР**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔮 VT: **{amount:.2f}**\n"
        f"🤖 Курс бота: **{format_num(bot_price)}** VC\n\n"
        f"Введи цену за 1 VT:"
    )


@router.message(MarketStates.waiting_sell_price)
async def market_sell_price(message: Message, state: FSMContext):
    price = parse_amount(message.text, 10**18)
    if price <= 0:
        await message.answer("❌ Введи корректную цену!")
        return

    data = await state.get_data()
    amount = data["sell_amount"]

    success = await db.create_market_order(message.from_user.id, "sell", amount, price)
    await state.clear()

    if success:
        xp = maybe_give_xp()
        if xp:
            await db.add_xp(message.from_user.id, xp)

        await message.answer(
            f"✅ **ОРДЕР СОЗДАН**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔮 **{amount:.2f}** VT\n"
            f"💰 **{format_num(price)}** VC/VT"
            + (f"\n⭐ +{xp} XP" if xp else "")
        )
    else:
        await message.answer("❌ Ошибка создания ордера!")


@router.callback_query(F.data == "mkt_my")
async def market_my(callback: CallbackQuery):
    orders = await db.get_user_market_orders(callback.from_user.id)

    text = "🔵 **МОИ ОРДЕРА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if orders:
        for o in orders:
            text += f"🔮 **{o['amount']:.2f}** VT по **{format_num(o['price_per_unit'])}** VC\n"
    else:
        text += "❌ Активных ордеров нет"

    kb = [[InlineKeyboardButton(text=f"❌ Отменить {o['amount']:.2f} VT", callback_data=f"mkt_cancel_{o['id']}")] for o in orders]
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="mkt_refresh")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data.startswith("mkt_cancel_"))
async def market_cancel(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    success = await db.cancel_market_order(callback.from_user.id, order_id)

    if success:
        await callback.answer("✅ Ордер отменён!", show_alert=True)
        await market_my(callback)
    else:
        await callback.answer("❌ Ошибка!", show_alert=True)
        # ==================== FARM ====================

@router.message(F.text.lower().in_(['ферма', 'майнинг', 'farm']))
async def farm_handler(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)

    gpus = await db.get_user_gpus(message.from_user.id)
    farm_stats = await db.get_farm_stats(message.from_user.id)

    total_per_hour = 0
    text = "⛏️ **ФЕРМА VT**\n━━━━━━━━━━━━━━━━━━━━\n\n"

    for gpu_key, gpu in GPU_CONFIG.items():
        user_gpu = next((g for g in gpus if g["gpu_type"] == gpu_key), None)
        count = user_gpu["count"] if user_gpu else 0
        prod = count * gpu["vibe_per_hour"]
        total_per_hour += prod
        price = await db.get_gpu_price(message.from_user.id, gpu_key, gpu["base_price"])

        text += (
            f"{gpu['emoji']} **{gpu['name']}**\n"
            f"└ {count}/10 | +{prod:.1f} VT/ч | {format_num(price)} VC\n\n"
        )

    accumulated = 0
    if farm_stats and farm_stats["last_collect"]:
        hours = (datetime.utcnow() - farm_stats["last_collect"]).total_seconds() / 3600
        accumulated = total_per_hour * hours

    kb = [
        [InlineKeyboardButton(text="🟢 GTX 1660", callback_data="farm_gtx1660")],
        [InlineKeyboardButton(text="🟡 RTX 3070", callback_data="farm_rtx3070")],
        [InlineKeyboardButton(text="🔴 RTX 4090", callback_data="farm_rtx4090")],
        [InlineKeyboardButton(text=f"💎 Собрать {accumulated:.2f} VT", callback_data="farm_collect")],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="sysinfo_farm")]
    ]

    text += f"⚡ Добыча: **{total_per_hour:.1f}** VT/ч\n💎 Накоплено: **{accumulated:.2f}** VT"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data == "sysinfo_farm")
async def sysinfo_farm(callback: CallbackQuery):
    await callback.answer(SYSTEM_INFOS["farm"], show_alert=True)


@router.callback_query(F.data.startswith("farm_"))
async def farm_callback(callback: CallbackQuery):
    action = callback.data.replace("farm_", "")

    if action == "collect":
        gpus = await db.get_user_gpus(callback.from_user.id)
        farm_stats = await db.get_farm_stats(callback.from_user.id)

        total_per_hour = sum(
            (next((g["count"] for g in gpus if g["gpu_type"] == key), 0) * value["vibe_per_hour"])
            for key, value in GPU_CONFIG.items()
        )

        if not farm_stats or not farm_stats["last_collect"]:
            await callback.answer("❌ Нечего собирать!", show_alert=True)
            return

        hours = (datetime.utcnow() - farm_stats["last_collect"]).total_seconds() / 3600
        accumulated = total_per_hour * hours

        if accumulated < 0.01:
            await callback.answer("⏰ Пока нечего собирать!", show_alert=True)
            return

        await db.collect_farm(callback.from_user.id, accumulated)

        xp = maybe_give_xp()
        if xp:
            await db.add_xp(callback.from_user.id, xp)

        await callback.answer(f"✅ +{accumulated:.2f} VT", show_alert=True)
        return

    if action not in GPU_CONFIG:
        return

    gpu = GPU_CONFIG[action]
    price = await db.get_gpu_price(callback.from_user.id, action, gpu["base_price"])
    success, result = await db.buy_gpu(callback.from_user.id, action, price)

    if success:
        xp = maybe_give_xp()
        if xp:
            await db.add_xp(callback.from_user.id, xp)
        await callback.answer(f"✅ Куплена {gpu['name']}!", show_alert=True)
    elif result == "max":
        await callback.answer("❌ Максимум 10 штук!", show_alert=True)
    else:
        await callback.answer("❌ Недостаточно VC!", show_alert=True)


# ==================== PRESIDENT ====================

@router.message(F.text.lower().in_(['президент', 'выборы']))
async def president_handler(message: Message):
    president = await db.get_president()
    elections = await db.get_today_elections()
    total_pool = await db.get_total_election_pool()

    current_name = "Никого"
    if president:
        current_name = president["username"] or president["first_name"] or str(president["user_id"])

    text = (
        f"👑 **ПРЕЗИДЕНТ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Текущий президент: **{current_name}**\n"
        f"💰 Налог: **0.01%** от всех операций\n\n"
        f"📊 Сегодняшний банк: **{format_num(total_pool)}** VC\n"
        f"👥 Участников: **{len(elections)}**\n\n"
        f"⏰ Ставки: 00:10 - 23:59 МСК\n"
        f"🕛 Итоги: 00:07 МСК"
    )

    kb = [
        [InlineKeyboardButton(text="💸 Сделать ставку", callback_data="pres_bet")],
        [InlineKeyboardButton(text="📋 Участники", callback_data="pres_members")],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="sysinfo_president")]
    ]

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data == "sysinfo_president")
async def sysinfo_president(callback: CallbackQuery):
    await callback.answer(SYSTEM_INFOS["president"], show_alert=True)


@router.callback_query(F.data == "pres_bet")
async def president_bet_start(callback: CallbackQuery, state: FSMContext):
    now = datetime.now(MSK)
    if now.hour == 0 and now.minute < 10:
        await callback.answer("❌ Ставки начнутся в 00:10 МСК!", show_alert=True)
        return

    president = await db.get_president()
    if president and president["user_id"] == callback.from_user.id:
        await callback.answer("❌ Текущий президент не может участвовать!", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)

    kb = [
        [
            InlineKeyboardButton(text="10к", callback_data="presamt_10000"),
            InlineKeyboardButton(text="100к", callback_data="presamt_100000"),
            InlineKeyboardButton(text="1кк", callback_data="presamt_1000000"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="pres_back")]
    ]

    await callback.message.edit_text(
        f"👑 **СТАВКА НА ВЫБОРЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Баланс: **{format_num(user['coins'])}** VC\n\n"
        f"Выбери сумму или отправь свою:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.set_state(ElectionStates.waiting_bet)


@router.callback_query(F.data.startswith("presamt_"))
async def president_bet_callback(callback: CallbackQuery, state: FSMContext):
    amount = int(callback.data.split("_")[1])
    success, error = await db.place_election_bet(callback.from_user.id, amount)
    await state.clear()

    if success:
        xp = maybe_give_xp()
        if xp:
            await db.add_xp(callback.from_user.id, xp)

        await callback.message.edit_text(
            f"✅ **СТАВКА ПРИНЯТА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💸 **{format_num(amount)}** VC поставлено"
            + (f"\n⭐ +{xp} XP" if xp else "")
        )
    else:
        errors = {
            "is_president": "❌ Президент не участвует!",
            "no_money": "❌ Недостаточно средств!"
        }
        await callback.answer(errors.get(error, "❌ Ошибка!"), show_alert=True)


@router.message(ElectionStates.waiting_bet)
async def president_bet_message(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(message.text, user["coins"])

    if amount <= 0:
        await message.answer("❌ Некорректная сумма!")
        return

    success, error = await db.place_election_bet(message.from_user.id, amount)
    await state.clear()

    if success:
        xp = maybe_give_xp()
        if xp:
            await db.add_xp(message.from_user.id, xp)

        await message.answer(
            f"✅ **СТАВКА ПРИНЯТА**\n\n"
            f"💸 **{format_num(amount)}** VC"
            + (f"\n⭐ +{xp} XP" if xp else "")
        )
    else:
        await message.answer("❌ Ошибка ставки!")


@router.callback_query(F.data == "pres_members")
async def president_members(callback: CallbackQuery):
    elections = await db.get_today_elections()
    total_pool = await db.get_total_election_pool()

    text = "📋 **УЧАСТНИКИ ВЫБОРОВ**\n━━━━━━━━━━━━━━━━━━━━\n\n"

    if elections:
        for e in elections[:30]:
            name = e["username"] or e["first_name"] or "Аноним"
            chance = (e["bet_amount"] / total_pool * 100) if total_pool > 0 else 0
            text += f"👤 {name}: **{format_num(e['bet_amount'])}** VC ({chance:.2f}%)\n"
    else:
        text += "❌ Пока нет участников"

    kb = [[InlineKeyboardButton(text="◀️ Назад", callback_data="pres_back")]]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data == "pres_back")
async def president_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    president = await db.get_president()
    elections = await db.get_today_elections()
    total_pool = await db.get_total_election_pool()

    current_name = "Никого"
    if president:
        current_name = president["username"] or president["first_name"] or str(president["user_id"])

    text = (
        f"👑 **ПРЕЗИДЕНТ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Текущий президент: **{current_name}**\n"
        f"💰 Налог: **0.01%** от всех операций\n\n"
        f"📊 Сегодняшний банк: **{format_num(total_pool)}** VC\n"
        f"👥 Участников: **{len(elections)}**\n\n"
        f"⏰ Ставки: 00:10 - 23:59 МСК\n"
        f"🕛 Итоги: 00:07 МСК"
    )

    kb = [
        [InlineKeyboardButton(text="💸 Сделать ставку", callback_data="pres_bet")],
        [InlineKeyboardButton(text="📋 Участники", callback_data="pres_members")],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="sysinfo_president")]
    ]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


# ==================== TOP ====================

@router.message(F.text.lower().in_(['топ', 'top', 'рейтинг']))
async def top_handler(message: Message):
    top_coins = await db.get_top_coins(10)
    top_vt = await db.get_top_vibeton(10)

    text = "🏆 **ТОПЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "💎 **По VC:**\n"
    medals = ['🥇', '🥈', '🥉']
    for i, user in enumerate(top_coins):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = user["first_name"] or user["username"] or "Аноним"
        text += f"{medal} {name}: **{format_num(user['coins'])}**\n"

    text += "\n🔮 **По VT:**\n"
    for i, user in enumerate(top_vt):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = user["first_name"] or user["username"] or "Аноним"
        text += f"{medal} {name}: **{user['vibeton']:.2f}**\n"

    await message.answer(text)


# ==================== PROMO ====================

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
        if result["coins_reward"] > 0:
            rewards.append(f"💎 {format_num(result['coins_reward'])} VC")
        if result["vibeton_reward"] > 0:
            rewards.append(f"🔮 {result['vibeton_reward']:.2f} VT")

        xp = maybe_give_xp()
        if xp:
            await db.add_xp(message.from_user.id, xp)

        await message.answer(
            f"🎁 **ПРОМОКОД АКТИВИРОВАН**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{' | '.join(rewards)}" + (f"\n⭐ +{xp} XP" if xp else "")
        )
    else:
        errors = {
            "not_found": "❌ Промокод не найден!",
            "expired": "❌ Промокод закончился!",
            "already_used": "❌ Уже использован!"
        }
        await message.answer(errors.get(result, "❌ Ошибка!"))


# ==================== HELP ====================

@router.message(CommandStart())
@router.message(F.text.lower().in_(['помощь', 'help', 'команды', 'хелп', 'start']))
async def help_handler(message: Message):
    await db.create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)

    kb = [
        [InlineKeyboardButton(text="🎮 Игры", callback_data="help_games")],
        [InlineKeyboardButton(text="💼 Системы", callback_data="help_systems")],
        [InlineKeyboardButton(text="👑 Президент", callback_data="help_president")]
    ]

    await message.answer(
        "🎮 **VIBEBOT**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Добро пожаловать!\n"
        "Выбери раздел:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
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
        "🎯 `дартс 100к`\n"
        "🎳 `боулинг 100к`\n"
        "🎰 `слоты 100к`\n"
        "🃏 `бд 100к`\n"
        "✂️ `кнб 100к`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="help_back")]
        ])
    )


@router.callback_query(F.data == "help_systems")
async def help_systems(callback: CallbackQuery):
    await callback.message.edit_text(
        "💼 **СИСТЕМЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 `я` — профиль\n"
        "💼 `работа` — список работ\n"
        "⛏️ `ферма` — майнинг VT\n"
        "🛒 `рынок` — торговля VT\n"
        "🏦 `банк` — депозит / переводы\n"
        "🏆 `топ` — топ игроков\n"
        "🎁 `промо КОД`\n\n"
        "⭐ За действия есть 25% шанс получить 1-2 XP",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="help_back")]
        ])
    )


@router.callback_query(F.data == "help_president")
async def help_president(callback: CallbackQuery):
    await callback.message.edit_text(
        "👑 **ПРЕЗИДЕНТ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "• Налог: 0.01%\n"
        "• Ставки: 00:10 - 23:59 МСК\n"
        "• Итоги: 00:07 МСК\n"
        "• Победитель случайный по весу ставок\n"
        "• Проигравшим 50% назад\n"
        "• Президент не участвует\n\n"
        "Команда: `президент`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="help_back")]
        ])
    )


@router.callback_query(F.data == "help_back")
async def help_back(callback: CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🎮 Игры", callback_data="help_games")],
        [InlineKeyboardButton(text="💼 Системы", callback_data="help_systems")],
        [InlineKeyboardButton(text="👑 Президент", callback_data="help_president")]
    ]

    await callback.message.edit_text(
        "🎮 **VIBEBOT**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Добро пожаловать!\n"
        "Выбери раздел:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
