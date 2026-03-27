import random
import asyncio
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from utils import format_num, parse_amount, maybe_give_xp

games_router = Router()


# ==================== INFO ====================

GAME_INFOS = {
    "mines": "💣 Мины — открывай безопасные клетки и забирай выигрыш до взрыва.",
    "diamond": "💎 Алмазы — угадывай, где алмаз, проходи уровни и забирай выигрыш.",
    "roulette": "🎡 Рулетка — красное, чёрное, зеро и диапазоны.",
    "crash": "📈 Краш — множитель растёт. Можно нажать «Забрать» до краша.",
    "dice": "🎲 Кости — угадай сумму двух кубиков: больше, меньше или ровно 7.",
    "football": "⚽ Футбол — угадай, будет гол или мимо.",
    "basketball": "🏀 Баскетбол — угадай, попадёт или промахнётся.",
    "darts": "🎯 Дартс — угадай сектор: центр, мимо, белое или красное.",
    "bowling": "🎳 Боулинг — угадай результат броска: 1, 3, 4, 5 или страйк.",
    "slots": "🎰 Слоты — Telegram анимация. 777 даёт большой выигрыш.",
    "blackjack": "🃏 Блекджек — набери 21 или число ближе к 21, чем у дилера.",
    "rps": "✂️ КНБ — камень, ножницы, бумага против бота."
}


@games_router.callback_query(F.data.startswith("info_"))
async def info_callback(callback: CallbackQuery):
    key = callback.data.replace("info_", "")
    text = GAME_INFOS.get(key, "ℹ️ Описание временно недоступно.")
    await callback.answer(text, show_alert=True)


@games_router.callback_query(F.data == "disabled")
async def disabled_callback(callback: CallbackQuery):
    await callback.answer()


# ==================== МИНЫ ====================

class MinesGame:
    @staticmethod
    def calculate_multiplier(opened: int, mines_count: int) -> float:
        table = {
            1: {1: 1.09, 2: 1.18, 3: 1.29, 4: 1.41, 5: 1.56, 6: 1.74},
            2: {1: 1.19, 2: 1.40, 3: 1.66, 4: 2.00, 5: 2.44, 6: 3.03},
            3: {1: 1.30, 2: 1.66, 3: 2.14, 4: 2.82, 5: 3.81, 6: 5.28},
            4: {1: 1.42, 2: 1.96, 3: 2.76, 4: 3.99, 5: 5.94, 6: 9.17},
            5: {1: 1.55, 2: 2.32, 3: 3.56, 4: 5.64, 5: 9.27, 6: 15.95},
            6: {1: 1.70, 2: 2.75, 3: 4.59, 4: 7.96, 5: 14.47, 6: 27.70},
            7: {1: 1.86, 2: 3.26, 3: 5.92, 4: 11.26, 5: 22.58, 6: 48.17},
            8: {1: 2.04, 2: 3.87, 3: 7.64, 4: 15.92, 5: 35.24, 6: 83.72},
            9: {1: 2.24, 2: 4.60, 3: 9.85, 4: 22.52, 5: 55.01, 6: 145.49},
            10: {1: 2.46, 2: 5.47, 3: 12.71, 4: 31.86, 5: 85.86, 6: 252.85},
        }
        return table.get(opened, {}).get(mines_count, 1.0)

    @staticmethod
    def keyboard(session_id: int, opened: list, mines: list, game_over=False):
        kb = []
        for row in range(5):
            line = []
            for col in range(5):
                cell = row * 5 + col
                if game_over:
                    if cell in mines:
                        text = "💣"
                    elif cell in opened:
                        text = "💎"
                    else:
                        text = "⬜"
                    cb = "disabled"
                else:
                    if cell in opened:
                        text = "💎"
                        cb = "disabled"
                    else:
                        text = "🟦"
                        cb = f"mines_{session_id}_{cell}"
                line.append(InlineKeyboardButton(text=text, callback_data=cb))
            kb.append(line)
        return kb


@games_router.message(lambda m: m.text and (m.text.lower().startswith("мины") or m.text.lower().startswith("/mines")))
async def mines_start(message: Message):
    text = message.text.lower().replace("/mines", "").replace("мины", "").strip()
    parts = text.split()

    if len(parts) < 1:
        await message.answer(
            "💣 **МИНЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `мины [ставка] [мины 1-6]`\n"
            "Пример: `мины 100к 5`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_mines")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    mines_count = 3
    if len(parts) >= 2 and parts[1].isdigit():
        mines_count = int(parts[1])
    if mines_count < 1 or mines_count > 6:
        mines_count = 3

    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    await db.update_coins(message.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp:
        await db.add_xp(message.from_user.id, xp)

    mines = random.sample(range(25), mines_count)
    state = {
        "bet": bet,
        "mines": mines,
        "opened": [],
        "mines_count": mines_count
    }
    session_id = await db.create_game_session(message.from_user.id, "mines", bet, state)

    kb = MinesGame.keyboard(session_id, [], mines, False)
    kb.append([InlineKeyboardButton(text="🎲 Случайная", callback_data=f"mines_random_{session_id}")])
    kb.append([InlineKeyboardButton(text="❓ Что это?", callback_data="info_mines")])

    await message.answer(
        f"💣 **МИНЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n"
        f"💣 Мин: **{mines_count}**\n"
        f"📈 Множитель: **x1.00**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@games_router.callback_query(F.data.startswith("mines_"))
async def mines_callback(callback: CallbackQuery):
    parts = callback.data.split("_")

    if parts[1] == "random":
        session_id = int(parts[2])
        session = await db.get_game_session(callback.from_user.id, "mines")
        if not session or session["id"] != session_id or not session["is_active"]:
            await callback.answer("❌ Игра не найдена!", show_alert=True)
            return

        state = json.loads(session["state"])
        safe = [i for i in range(25) if i not in state["opened"] and i not in state["mines"]]
        if not safe:
            await callback.answer("❌ Нет доступных клеток!", show_alert=True)
            return
        cell = random.choice(safe)
    elif parts[1] == "cashout":
        session_id = int(parts[2])
        session = await db.get_game_session(callback.from_user.id, "mines")
        if not session or session["id"] != session_id or not session["is_active"]:
            await callback.answer("❌ Игра не найдена!", show_alert=True)
            return

        state = json.loads(session["state"])
        opened = len(state["opened"])
        if opened == 0:
            await callback.answer("❌ Сначала открой клетку!", show_alert=True)
            return

        mult = MinesGame.calculate_multiplier(opened, state["mines_count"])
        win = int(state["bet"] * mult)

        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await db.close_game_session(session_id)

        kb = MinesGame.keyboard(session_id, state["opened"], state["mines"], True)
        await callback.message.edit_text(
            f"💣 **МИНЫ — ЗАБРАЛ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Открыто: **{opened}**\n"
            f"📈 x**{mult:.2f}**\n\n"
            f"🏆 **+{format_num(win)}** VC",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        return
    else:
        session_id = int(parts[1])
        cell = int(parts[2])
        session = await db.get_game_session(callback.from_user.id, "mines")
        if not session or session["id"] != session_id or not session["is_active"]:
            await callback.answer("❌ Игра не найдена!", show_alert=True)
            return

        state = json.loads(session["state"])

    if cell in state["mines"]:
        state["opened"].append(cell)
        await db.update_stats(callback.from_user.id, False, state["bet"])
        await db.close_game_session(session_id)

        kb = MinesGame.keyboard(session_id, state["opened"], state["mines"], True)
        await callback.message.edit_text(
            f"💣 **МИНЫ — ВЗРЫВ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💔 **-{format_num(state['bet'])}** VC",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        await callback.answer("💥 Мина!", show_alert=True)
        return

    if cell not in state["opened"]:
        state["opened"].append(cell)

    opened = len(state["opened"])
    mult = MinesGame.calculate_multiplier(opened, state["mines_count"])
    win = int(state["bet"] * mult)

    if opened >= 25 - state["mines_count"]:
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await db.close_game_session(session_id)

        kb = MinesGame.keyboard(session_id, state["opened"], state["mines"], True)
        await callback.message.edit_text(
            f"💣 **МИНЫ — ПОБЕДА!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏆 **+{format_num(win)}** VC",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        return

    await db.update_game_session(session_id, state, True)

    kb = MinesGame.keyboard(session_id, state["opened"], state["mines"], False)
    kb.append([InlineKeyboardButton(text=f"💰 Забрать {format_num(win)}", callback_data=f"mines_cashout_{session_id}")])
    kb.append([InlineKeyboardButton(text="🎲 Случайная", callback_data=f"mines_random_{session_id}")])
    kb.append([InlineKeyboardButton(text="❓ Что это?", callback_data="info_mines")])

    await callback.message.edit_text(
        f"💣 **МИНЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✨ Открыто: **{opened}**\n"
        f"📈 x**{mult:.2f}**\n"
        f"💵 Забрать: **{format_num(win)}** VC",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await callback.answer("✅ Безопасно!")


# ==================== АЛМАЗЫ ====================

class DiamondGame:
    @staticmethod
    def get_size(diff: int):
        return 3 if diff == 1 else 4

    @staticmethod
    def get_multiplier(level: int, diff: int):
        if diff == 1:
            table = {1: 1.08, 2: 1.17, 3: 1.27, 4: 1.38, 5: 1.50, 6: 1.63, 7: 1.77, 8: 1.92, 9: 2.09, 10: 2.27, 11: 2.47, 12: 2.68, 13: 2.92, 14: 3.17, 15: 3.45, 16: 3.75}
        else:
            table = {1: 1.13, 2: 1.28, 3: 1.45, 4: 1.64, 5: 1.86, 6: 2.11, 7: 2.39, 8: 2.71, 9: 3.07, 10: 3.48, 11: 3.95, 12: 4.48, 13: 5.08, 14: 5.76, 15: 6.53, 16: 7.41}
        return table.get(level, 1.0)

    @staticmethod
    def keyboard(session_id: int, size: int, diamond: int, reveal=False, wrong=-1):
        kb = []
        for row in range(size):
            line = []
            for col in range(size):
                idx = row * size + col
                if reveal:
                    if idx == diamond:
                        text = "💎"
                    elif idx == wrong:
                        text = "❌"
                    else:
                        text = "⬜"
                    cb = "disabled"
                else:
                    text = "🟦"
                    cb = f"diamond_{session_id}_{idx}"
                line.append(InlineKeyboardButton(text=text, callback_data=cb))
            kb.append(line)
        return kb


@games_router.message(lambda m: m.text and (m.text.lower().startswith("алмаз") or m.text.lower().startswith("/diamond")))
async def diamond_start(message: Message):
    text = message.text.lower().replace("/diamond", "").replace("алмазы", "").replace("алмаз", "").strip()
    parts = text.split()

    if len(parts) < 1:
        await message.answer(
            "💎 **АЛМАЗЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `алмазы [ставка] [сложность 1-2]`\n"
            "Пример: `алмазы 100к 2`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_diamond")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    diff = 1
    if len(parts) >= 2 and parts[1] in ["1", "2"]:
        diff = int(parts[1])

    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    await db.update_coins(message.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp:
        await db.add_xp(message.from_user.id, xp)

    size = DiamondGame.get_size(diff)
    diamond = random.randint(0, size * size - 1)
    state = {"bet": bet, "difficulty": diff, "level": 1, "size": size, "diamond": diamond}
    session_id = await db.create_game_session(message.from_user.id, "diamonds", bet, state)

    kb = DiamondGame.keyboard(session_id, size, diamond, False)
    kb.append([InlineKeyboardButton(text="❓ Что это?", callback_data="info_diamond")])

    await message.answer(
        f"💎 **АЛМАЗЫ** — Уровень 1/16\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n"
        f"📈 x**{DiamondGame.get_multiplier(1, diff):.2f}**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@games_router.callback_query(F.data.startswith("diamond_"))
async def diamond_callback(callback: CallbackQuery):
    parts = callback.data.split("_")

    if parts[1] == "cashout":
        session_id = int(parts[2])
        session = await db.get_game_session(callback.from_user.id, "diamonds")
        if not session or session["id"] != session_id or not session["is_active"]:
            await callback.answer("❌ Игра не найдена!", show_alert=True)
            return

        state = json.loads(session["state"])
        if state["level"] <= 1:
            await callback.answer("❌ Пройди хотя бы 1 уровень!", show_alert=True)
            return

        mult = DiamondGame.get_multiplier(state["level"] - 1, state["difficulty"])
        win = int(state["bet"] * mult)

        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await db.close_game_session(session_id)

        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ — ЗАБРАЛ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Уровней: **{state['level'] - 1}**\n"
            f"📈 x**{mult:.2f}**\n\n"
            f"🏆 **+{format_num(win)}** VC"
        )
        return

    session_id = int(parts[1])
    cell = int(parts[2])

    session = await db.get_game_session(callback.from_user.id, "diamonds")
    if not session or session["id"] != session_id or not session["is_active"]:
        await callback.answer("❌ Игра не найдена!", show_alert=True)
        return

    state = json.loads(session["state"])

    if cell != state["diamond"]:
        await db.update_stats(callback.from_user.id, False, state["bet"])
        await db.close_game_session(session_id)

        kb = DiamondGame.keyboard(session_id, state["size"], state["diamond"], True, cell)
        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ — ПРОИГРЫШ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💔 **-{format_num(state['bet'])}** VC",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        await callback.answer("❌ Не угадал!", show_alert=True)
        return

    state["level"] += 1

    if state["level"] > 16:
        mult = DiamondGame.get_multiplier(16, state["difficulty"])
        win = int(state["bet"] * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await db.close_game_session(session_id)

        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ — ДЖЕКПОТ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎉 Пройдены все уровни!\n\n"
            f"🏆 **+{format_num(win)}** VC"
        )
        return

    size = DiamondGame.get_size(state["difficulty"])
    state["size"] = size
    state["diamond"] = random.randint(0, size * size - 1)
    await db.update_game_session(session_id, state, True)

    prev_mult = DiamondGame.get_multiplier(state["level"] - 1, state["difficulty"])
    prev_win = int(state["bet"] * prev_mult)

    kb = DiamondGame.keyboard(session_id, size, state["diamond"], False)
    kb.append([InlineKeyboardButton(text=f"💰 Забрать {format_num(prev_win)}", callback_data=f"diamond_cashout_{session_id}")])
    kb.append([InlineKeyboardButton(text="❓ Что это?", callback_data="info_diamond")])

    await callback.message.edit_text(
        f"💎 **АЛМАЗЫ** — Уровень {state['level']}/16\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Угадал!\n"
        f"📈 x**{DiamondGame.get_multiplier(state['level'], state['difficulty']):.2f}**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await callback.answer("✅ Алмаз найден!")


# ==================== РУЛЕТКА ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith("рулетка"))
async def roulette_start(message: Message):
    parts = message.text.lower().replace("рулетка", "").strip().split()

    if len(parts) < 1:
        await message.answer(
            "🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `рулетка [ставка]`\n"
            "Пример: `рулетка 100к`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_roulette")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    kb = [
        [
            InlineKeyboardButton(text="🔴 Красное x2", callback_data=f"rlt_{bet}_red"),
            InlineKeyboardButton(text="⚫ Чёрное x2", callback_data=f"rlt_{bet}_black"),
        ],
        [InlineKeyboardButton(text="🟢 Зеро x36", callback_data=f"rlt_{bet}_zero")],
        [
            InlineKeyboardButton(text="1-12 x3", callback_data=f"rlt_{bet}_1-12"),
            InlineKeyboardButton(text="13-24 x3", callback_data=f"rlt_{bet}_13-24"),
            InlineKeyboardButton(text="25-36 x3", callback_data=f"rlt_{bet}_25-36"),
        ],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_roulette")]
    ]

    await message.answer(
        f"🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n\n"
        f"🎯 Выбери ставку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@games_router.callback_query(F.data.startswith("rlt_"))
async def roulette_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    bet = int(parts[1])
    choice = parts[2]

    user = await db.get_user(callback.from_user.id)
    if user["coins"] < bet:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.update_coins(callback.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text("🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n🎰 Крутим...")
    await asyncio.sleep(2)

    result = random.randint(0, 36)
    red = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    color = "🟢" if result == 0 else ("🔴" if result in red else "⚫")

    won = False
    mult = 0

    if choice == "red" and result in red:
        won, mult = True, 2
    elif choice == "black" and result not in red and result != 0:
        won, mult = True, 2
    elif choice == "zero" and result == 0:
        won, mult = True, 36
    elif choice == "1-12" and 1 <= result <= 12:
        won, mult = True, 3
    elif choice == "13-24" and 13 <= result <= 24:
        won, mult = True, 3
    elif choice == "25-36" and 25 <= result <= 36:
        won, mult = True, 3

    if won:
        win = bet * mult
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.edit_text(
            f"🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{color} Выпало: **{result}**\n\n"
            f"✅ x{mult}\n🏆 **+{format_num(win)}** VC"
        )
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.edit_text(
            f"🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{color} Выпало: **{result}**\n\n"
            f"❌ **-{format_num(bet)}** VC"
        )


# ==================== КРАШ ====================

def crash_keyboard(session_id: int, active: bool = True):
    rows = []
    if active:
        rows.append([InlineKeyboardButton(text="💰 Забрать", callback_data=f"crash_cash_{session_id}")])
    rows.append([InlineKeyboardButton(text="❓ Что это?", callback_data="info_crash")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@games_router.message(lambda m: m.text and m.text.lower().startswith("краш"))
async def crash_start(message: Message):
    parts = message.text.lower().replace("краш", "").strip().split()

    if len(parts) < 2:
        await message.answer(
            "📈 **КРАШ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `краш [ставка] [вывод]`\n"
            "Пример: `краш 100к 2.5`\n"
            "Диапазон: 1.01 - 505",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_crash")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    try:
        cashout = float(parts[1].replace("x", "").replace(",", "."))
    except:
        await message.answer("❌ Неверный множитель!")
        return

    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return
    if cashout < 1.01 or cashout > 505:
        await message.answer("❌ Множитель должен быть от 1.01 до 505!")
        return

    await db.update_coins(message.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp:
        await db.add_xp(message.from_user.id, xp)

    r = random.random()
    if r < 0.40:
        crash_point = round(random.uniform(1.00, 1.50), 2)
    elif r < 0.70:
        crash_point = round(random.uniform(1.50, 3.00), 2)
    elif r < 0.88:
        crash_point = round(random.uniform(3.00, 10.00), 2)
    elif r < 0.97:
        crash_point = round(random.uniform(10.00, 100.00), 2)
    else:
        crash_point = round(random.uniform(100.00, 505.00), 2)

    state = {
        "bet": bet,
        "target": cashout,
        "current": 1.00,
        "crash_point": crash_point,
        "cashed_out": False,
        "cashout_value": 0
    }
    session_id = await db.create_game_session(message.from_user.id, "crash", bet, state)

    msg = await message.answer(
        f"📈 **КРАШ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n"
        f"🎯 Автостоп: **x{cashout}**\n\n"
        f"🚀 x**1.00**",
        reply_markup=crash_keyboard(session_id, True)
    )

    current = 1.00
    step = 0.03
    auto_closed = False

    while current < crash_point:
        await asyncio.sleep(0.25)
        current = round(current + step, 2)
        step *= 1.05
        if current > crash_point:
            current = crash_point

        session = await db.get_game_session_by_id(session_id)
        if not session:
            break
        state = json.loads(session["state"])

        state["current"] = current

        if not state["cashed_out"] and current >= state["target"]:
            state["cashed_out"] = True
            state["cashout_value"] = state["target"]
            auto_closed = True
            win = int(state["bet"] * state["target"])
            await db.update_coins(callback.from_user.id if False else message.from_user.id, win)
            await db.update_stats(message.from_user.id, True, win)

        await db.update_game_session(session_id, state, True)

        bar_len = min(20, int((current / max(1.01, min(state["target"], crash_point))) * 20))
        bar = "█" * bar_len + "░" * (20 - bar_len)

        # если игрок уже забрал, игра для него окончена, но визуал продолжается
        status_line = ""
        if state["cashed_out"]:
            status_line = f"\n💰 Забрано на x**{state['cashout_value']}**"

        try:
            await msg.edit_text(
                f"📈 **КРАШ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 **{format_num(state['bet'])}** VC\n"
                f"🚀 x**{current}**\n"
                f"[{bar}]"
                f"{status_line}",
                reply_markup=crash_keyboard(session_id, False if state["cashed_out"] else True)
            )
        except:
            pass

    session = await db.get_game_session_by_id(session_id)
    if session:
        state = json.loads(session["state"])
        await db.close_game_session(session_id)

        if state["cashed_out"]:
            win = int(state["bet"] * state["cashout_value"])
            try:
                await msg.edit_text(
                    f"📈 **КРАШ — ЗАБРАЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💰 Ставка: **{format_num(state['bet'])}** VC\n"
                    f"✅ Забрано на x**{state['cashout_value']}**\n"
                    f"💥 Крашнуло на x**{crash_point}**\n\n"
                    f"🏆 **+{format_num(win)}** VC",
                    reply_markup=crash_keyboard(session_id, False)
                )
            except:
                pass
        else:
            await db.update_stats(message.from_user.id, False, state["bet"])
            try:
                await msg.edit_text(
                    f"📈 **КРАШ — КРАХ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💥 Краш на x**{crash_point}**\n\n"
                    f"❌ **-{format_num(state['bet'])}** VC",
                    reply_markup=crash_keyboard(session_id, False)
                )
            except:
                pass


@games_router.callback_query(F.data.startswith("crash_cash_"))
async def crash_cashout(callback: CallbackQuery):
    session_id = int(callback.data.split("_")[2])
    session = await db.get_game_session_by_id(session_id)
    if not session or not session["is_active"]:
        await callback.answer("❌ Игра уже закончена!", show_alert=True)
        return

    state = json.loads(session["state"])
    if state["cashed_out"]:
        await callback.answer("✅ Уже забрано!", show_alert=True)
        return

    current = max(1.01, float(state["current"]))
    state["cashed_out"] = True
    state["cashout_value"] = round(current, 2)

    win = int(state["bet"] * state["cashout_value"])
    await db.update_coins(callback.from_user.id, win)
    await db.update_stats(callback.from_user.id, True, win)
    await db.update_game_session(session_id, state, True)

    await callback.answer(f"💰 Забрано на x{state['cashout_value']}", show_alert=True)
    # ==================== КОСТИ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith("кости"))
async def dice_start(message: Message):
    parts = message.text.lower().replace("кости", "").strip().split()

    if len(parts) < 1:
        await message.answer(
            "🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `кости [ставка]`\n"
            "Пример: `кости 100к`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_dice")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    kb = [
        [
            InlineKeyboardButton(text="🟢 Больше 7 x2.3", callback_data=f"dice_{bet}_more"),
            InlineKeyboardButton(text="🔵 Меньше 7 x2.3", callback_data=f"dice_{bet}_less"),
        ],
        [InlineKeyboardButton(text="🟡 Ровно 7 x5.8", callback_data=f"dice_{bet}_exact")],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_dice")]
    ]

    await message.answer(
        f"🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n\n"
        f"🎯 Выбери исход:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@games_router.callback_query(F.data.startswith("dice_"))
async def dice_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    bet = int(parts[1])
    choice = parts[2]

    user = await db.get_user(callback.from_user.id)
    if not user or user["coins"] < bet:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.update_coins(callback.from_user.id, -bet)

    xp = maybe_give_xp()
    if xp:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text("🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎰 Бросаем кубики...")

    d1 = await callback.message.answer_dice(emoji="🎲")
    await asyncio.sleep(0.6)
    d2 = await callback.message.answer_dice(emoji="🎲")
    await asyncio.sleep(4)

    total = d1.dice.value + d2.dice.value

    won = False
    mult = 0

    if choice == "more" and total > 7:
        won, mult = True, 2.3
    elif choice == "less" and total < 7:
        won, mult = True, 2.3
    elif choice == "exact" and total == 7:
        won, mult = True, 5.8

    if won:
        win = int(bet * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.answer(
            f"🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 Выпало: **{d1.dice.value} + {d2.dice.value} = {total}**\n\n"
            f"✅ Победа x**{mult}**\n"
            f"🏆 **+{format_num(win)}** VC"
        )
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.answer(
            f"🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 Выпало: **{d1.dice.value} + {d2.dice.value} = {total}**\n\n"
            f"❌ **-{format_num(bet)}** VC"
        )


# ==================== ФУТБОЛ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith("футбол"))
async def football_start(message: Message):
    parts = message.text.lower().replace("футбол", "").strip().split()

    if len(parts) < 1:
        await message.answer(
            "⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `футбол [ставка]`\n"
            "Пример: `футбол 100к`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_football")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    kb = [
        [
            InlineKeyboardButton(text="🟢 Гол x1.8", callback_data=f"foot_{bet}_goal"),
            InlineKeyboardButton(text="🔴 Мимо x3.7", callback_data=f"foot_{bet}_miss"),
        ],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_football")]
    ]

    await message.answer(
        f"⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n\n"
        f"🎯 Выбери исход:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@games_router.callback_query(F.data.startswith("foot_"))
async def football_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    bet = int(parts[1])
    choice = parts[2]

    user = await db.get_user(callback.from_user.id)
    if not user or user["coins"] < bet:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.update_coins(callback.from_user.id, -bet)

    xp = maybe_give_xp()
    if xp:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text("⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n🏃 Удар...")
    dice = await callback.message.answer_dice(emoji="⚽")
    await asyncio.sleep(4)

    is_goal = dice.dice.value >= 3
    won = (choice == "goal" and is_goal) or (choice == "miss" and not is_goal)
    mult = 1.8 if choice == "goal" else 3.7
    result_text = "⚽ Гол!" if is_goal else "❌ Мимо!"

    if won:
        win = int(bet * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.answer(
            f"⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{result_text}\n\n"
            f"✅ Победа x**{mult}**\n"
            f"🏆 **+{format_num(win)}** VC"
        )
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.answer(
            f"⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{result_text}\n\n"
            f"❌ **-{format_num(bet)}** VC"
        )


# ==================== БАСКЕТБОЛ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith("баскетбол"))
async def basketball_start(message: Message):
    parts = message.text.lower().replace("баскетбол", "").strip().split()

    if len(parts) < 1:
        await message.answer(
            "🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `баскетбол [ставка]`\n"
            "Пример: `баскетбол 100к`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_basketball")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    kb = [
        [
            InlineKeyboardButton(text="🟢 Гол x3.8", callback_data=f"bask_{bet}_goal"),
            InlineKeyboardButton(text="🔴 Мимо x1.9", callback_data=f"bask_{bet}_miss"),
        ],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_basketball")]
    ]

    await message.answer(
        f"🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n\n"
        f"🎯 Выбери исход:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@games_router.callback_query(F.data.startswith("bask_"))
async def basketball_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    bet = int(parts[1])
    choice = parts[2]

    user = await db.get_user(callback.from_user.id)
    if not user or user["coins"] < bet:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.update_coins(callback.from_user.id, -bet)

    xp = maybe_give_xp()
    if xp:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text("🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n🏃 Бросок...")
    dice = await callback.message.answer_dice(emoji="🏀")
    await asyncio.sleep(4)

    is_goal = dice.dice.value >= 4
    won = (choice == "goal" and is_goal) or (choice == "miss" and not is_goal)
    mult = 3.8 if choice == "goal" else 1.9
    result_text = "🏀 Гол!" if is_goal else "❌ Мимо!"

    if won:
        win = int(bet * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.answer(
            f"🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{result_text}\n\n"
            f"✅ Победа x**{mult}**\n"
            f"🏆 **+{format_num(win)}** VC"
        )
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.answer(
            f"🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{result_text}\n\n"
            f"❌ **-{format_num(bet)}** VC"
        )


# ==================== ДАРТС ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith("дартс"))
async def darts_start(message: Message):
    parts = message.text.lower().replace("дартс", "").strip().split()

    if len(parts) < 1:
        await message.answer(
            "🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `дартс [ставка]`\n"
            "Пример: `дартс 100к`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_darts")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    kb = [
        [
            InlineKeyboardButton(text="🟡 Центр x5.8", callback_data=f"dart_{bet}_center"),
            InlineKeyboardButton(text="⚪ Белое x1.9", callback_data=f"dart_{bet}_white"),
        ],
        [
            InlineKeyboardButton(text="🔴 Красное x1.9", callback_data=f"dart_{bet}_red"),
            InlineKeyboardButton(text="❌ Мимо x5.8", callback_data=f"dart_{bet}_miss"),
        ],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_darts")]
    ]

    await message.answer(
        f"🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n\n"
        f"🎯 Выбери исход:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@games_router.callback_query(F.data.startswith("dart_"))
async def darts_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    bet = int(parts[1])
    choice = parts[2]

    user = await db.get_user(callback.from_user.id)
    if not user or user["coins"] < bet:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.update_coins(callback.from_user.id, -bet)

    xp = maybe_give_xp()
    if xp:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text("🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n🏹 Бросок...")
    dice = await callback.message.answer_dice(emoji="🎯")
    await asyncio.sleep(4)

    value = dice.dice.value
    if value == 6:
        result = "center"
        result_text = "🟡 Центр"
    elif value == 1:
        result = "miss"
        result_text = "❌ Мимо"
    elif value in [2, 3]:
        result = "white"
        result_text = "⚪ Белое"
    else:
        result = "red"
        result_text = "🔴 Красное"

    mult_map = {"center": 5.8, "miss": 5.8, "white": 1.9, "red": 1.9}
    won = choice == result
    mult = mult_map[choice]

    if won:
        win = int(bet * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.answer(
            f"🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Результат: **{result_text}**\n\n"
            f"✅ Победа x**{mult}**\n"
            f"🏆 **+{format_num(win)}** VC"
        )
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.answer(
            f"🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Результат: **{result_text}**\n\n"
            f"❌ **-{format_num(bet)}** VC"
        )


# ==================== БОУЛИНГ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith("боулинг"))
async def bowling_start(message: Message):
    parts = message.text.lower().replace("боулинг", "").strip().split()

    if len(parts) < 1:
        await message.answer(
            "🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `боулинг [ставка]`\n"
            "Пример: `боулинг 100к`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_bowling")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    kb = [
        [
            InlineKeyboardButton(text="1️⃣ x2.3", callback_data=f"bowl_{bet}_1"),
            InlineKeyboardButton(text="3️⃣ x2.3", callback_data=f"bowl_{bet}_3"),
            InlineKeyboardButton(text="4️⃣ x2.3", callback_data=f"bowl_{bet}_4"),
        ],
        [
            InlineKeyboardButton(text="5️⃣ x2.3", callback_data=f"bowl_{bet}_5"),
            InlineKeyboardButton(text="6️⃣ Страйк x5.3", callback_data=f"bowl_{bet}_6"),
        ],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_bowling")]
    ]

    await message.answer(
        f"🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n\n"
        f"🎯 Угадай количество:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@games_router.callback_query(F.data.startswith("bowl_"))
async def bowling_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    bet = int(parts[1])
    choice = parts[2]

    user = await db.get_user(callback.from_user.id)
    if not user or user["coins"] < bet:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.update_coins(callback.from_user.id, -bet)

    xp = maybe_give_xp()
    if xp:
        await db.add_xp(callback.from_user.id, xp)

    await callback.message.edit_text("🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎳 Бросок...")
    dice = await callback.message.answer_dice(emoji="🎳")
    await asyncio.sleep(4)

    result = str(dice.dice.value)
    mult = 5.3 if choice == "6" else 2.3

    if result == choice:
        win = int(bet * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.answer(
            f"🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Результат: **{result}**\n\n"
            f"✅ Победа x**{mult}**\n"
            f"🏆 **+{format_num(win)}** VC"
        )
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.answer(
            f"🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Результат: **{result}**\n\n"
            f"❌ **-{format_num(bet)}** VC"
        )


# ==================== СЛОТЫ ====================

@games_router.message(lambda m: m.text and (m.text.lower().startswith("слот") or m.text.lower().startswith("слоты")))
async def slots_start(message: Message):
    text = message.text.lower().replace("слоты", "").replace("слот", "").strip()
    parts = text.split()

    if len(parts) < 1:
        await message.answer(
            "🎰 **СЛОТЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `слоты [ставка]`\n"
            "Пример: `слоты 100к`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_slots")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    await db.update_coins(message.from_user.id, -bet)

    xp = maybe_give_xp()
    if xp:
        await db.add_xp(message.from_user.id, xp)

    await message.answer("🎰 **СЛОТЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎲 Крутим...")
    dice = await message.answer_dice(emoji="🎰")
    await asyncio.sleep(4)

    value = dice.dice.value
    win = 0
    result_text = "❌ Нет совпадений"

    # Telegram slot special values
    if value in [64]:
        win = bet * 50
        result_text = "🎰 **777 — ДЖЕКПОТ!**"
    elif value in [1, 22, 43]:
        win = bet * 20
        result_text = "🔥 **Сильная комбинация!**"
    elif value in [16, 32, 48]:
        win = bet * 10
        result_text = "✨ **Три одинаковых!**"
    elif value in [2, 3, 4, 17, 18, 33, 34, 49, 50]:
        win = bet * 2
        result_text = "🎉 **Два совпадения!**"

    if win > 0:
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await message.answer(
            f"🎰 **СЛОТЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{result_text}\n\n"
            f"🏆 **+{format_num(win)}** VC"
        )
    else:
        await db.update_stats(message.from_user.id, False, bet)
        await message.answer(
            f"🎰 **СЛОТЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{result_text}\n\n"
            f"❌ **-{format_num(bet)}** VC"
        )


# ==================== КНБ ====================

RPS_MAP = {
    "rock": "🪨 Камень",
    "paper": "📄 Бумага",
    "scissors": "✂️ Ножницы"
}


@games_router.message(lambda m: m.text and (m.text.lower().startswith("кнб") or m.text.lower().startswith("камень ножницы бумага")))
async def rps_start(message: Message):
    text = message.text.lower().replace("кнб", "").replace("камень ножницы бумага", "").strip()
    parts = text.split()

    if len(parts) < 1:
        await message.answer(
            "✂️ **КНБ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `кнб [ставка]`\n"
            "Пример: `кнб 100к`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_rps")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    kb = [
        [
            InlineKeyboardButton(text="🪨 Камень", callback_data=f"rps_{bet}_rock"),
            InlineKeyboardButton(text="📄 Бумага", callback_data=f"rps_{bet}_paper"),
            InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"rps_{bet}_scissors"),
        ],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_rps")]
    ]

    await message.answer(
        f"✂️ **КНБ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n\n"
        f"Выбери ход:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@games_router.callback_query(F.data.startswith("rps_"))
async def rps_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    bet = int(parts[1])
    player = parts[2]

    user = await db.get_user(callback.from_user.id)
    if not user or user["coins"] < bet:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.update_coins(callback.from_user.id, -bet)

    xp = maybe_give_xp()
    if xp:
        await db.add_xp(callback.from_user.id, xp)

    bot = random.choice(["rock", "paper", "scissors"])

    if player == bot:
        await db.update_coins(callback.from_user.id, bet)
        result = "🤝 Ничья!"
        reward = f"↩️ Возврат **{format_num(bet)}** VC"
    elif (
        (player == "rock" and bot == "scissors") or
        (player == "paper" and bot == "rock") or
        (player == "scissors" and bot == "paper")
    ):
        win = bet * 2
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        result = "✅ Победа!"
        reward = f"🏆 **+{format_num(win)}** VC"
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        result = "❌ Проигрыш!"
        reward = f"💔 **-{format_num(bet)}** VC"

    await callback.message.edit_text(
        f"✂️ **КНБ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Ты: **{RPS_MAP[player]}**\n"
        f"Бот: **{RPS_MAP[bot]}**\n\n"
        f"{result}\n{reward}"
    )


# ==================== БЛЕКДЖЕК ====================

class Blackjack:
    cards = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'] * 4

    @staticmethod
    def value(hand):
        total = 0
        aces = 0
        for c in hand:
            if c in ['J', 'Q', 'K']:
                total += 10
            elif c == 'A':
                aces += 1
                total += 11
            else:
                total += int(c)

        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        return total

    @staticmethod
    def draw(deck):
        return deck.pop(random.randint(0, len(deck) - 1))

    @staticmethod
    def pretty(hand):
        return " ".join(hand)


@games_router.message(lambda m: m.text and (m.text.lower().startswith("бд") or m.text.lower().startswith("блекджек") or m.text.lower().startswith("blackjack")))
async def bj_start(message: Message):
    text = message.text.lower().replace("блекджек", "").replace("blackjack", "").replace("бд", "").strip()
    parts = text.split()

    if len(parts) < 1:
        await message.answer(
            "🃏 **БЛЕКДЖЕК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Использование: `бд [ставка]`\n"
            "Пример: `бд 100к`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Что это?", callback_data="info_blackjack")]
            ])
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    bet = parse_amount(parts[0], user["coins"])
    if bet <= 0 or bet > user["coins"]:
        await message.answer("❌ Некорректная ставка!")
        return

    await db.update_coins(message.from_user.id, -bet)

    xp = maybe_give_xp()
    if xp:
        await db.add_xp(message.from_user.id, xp)

    deck = Blackjack.cards.copy()
    random.shuffle(deck)

    player = [Blackjack.draw(deck), Blackjack.draw(deck)]
    dealer = [Blackjack.draw(deck), Blackjack.draw(deck)]

    state = {
        "deck": deck,
        "player": player,
        "dealer": dealer,
        "bet": bet
    }

    session_id = await db.create_game_session(message.from_user.id, "blackjack", bet, state)

    player_val = Blackjack.value(player)
    dealer_hidden = dealer[0]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Ещё", callback_data=f"bj_hit_{session_id}"),
            InlineKeyboardButton(text="✋ Хватит", callback_data=f"bj_stand_{session_id}"),
        ],
        [InlineKeyboardButton(text="❓ Что это?", callback_data="info_blackjack")]
    ])

    await message.answer(
        f"🃏 **БЛЕКДЖЕК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Ты: {Blackjack.pretty(player)} (**{player_val}**)\n"
        f"🤖 Дилер: {dealer_hidden} ❓",
        reply_markup=kb
    )


@games_router.callback_query(F.data.startswith("bj_"))
async def bj_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    action = parts[1]
    session_id = int(parts[2])

    session = await db.get_game_session(callback.from_user.id, "blackjack")
    if not session or session["id"] != session_id or not session["is_active"]:
        await callback.answer("❌ Игра не найдена!", show_alert=True)
        return

    state = json.loads(session["state"])
    player = state["player"]
    dealer = state["dealer"]
    deck = state["deck"]
    bet = state["bet"]

    if action == "hit":
        player.append(Blackjack.draw(deck))
        player_val = Blackjack.value(player)

        if player_val > 21:
            await db.update_stats(callback.from_user.id, False, bet)
            await db.close_game_session(session_id)
            await callback.message.edit_text(
                f"🃏 **БЛЕКДЖЕК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 Ты: {Blackjack.pretty(player)} (**{player_val}**)\n\n"
                f"💥 Перебор!\n"
                f"❌ **-{format_num(bet)}** VC"
            )
            return

        state["player"] = player
        state["deck"] = deck
        await db.update_game_session(session_id, state, True)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📥 Ещё", callback_data=f"bj_hit_{session_id}"),
                InlineKeyboardButton(text="✋ Хватит", callback_data=f"bj_stand_{session_id}"),
            ],
            [InlineKeyboardButton(text="❓ Что это?", callback_data="info_blackjack")]
        ])

        await callback.message.edit_text(
            f"🃏 **БЛЕКДЖЕК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Ты: {Blackjack.pretty(player)} (**{player_val}**)\n"
            f"🤖 Дилер: {dealer[0]} ❓",
            reply_markup=kb
        )
        return

    if action == "stand":
        player_val = Blackjack.value(player)
        dealer_val = Blackjack.value(dealer)

        while dealer_val < 17:
            dealer.append(Blackjack.draw(deck))
            dealer_val = Blackjack.value(dealer)

        await db.close_game_session(session_id)

        if dealer_val > 21 or player_val > dealer_val:
            win = bet * 2
            await db.update_coins(callback.from_user.id, win)
            await db.update_stats(callback.from_user.id, True, win)
            result = f"✅ Победа!\n🏆 **+{format_num(win)}** VC"
        elif player_val == dealer_val:
            await db.update_coins(callback.from_user.id, bet)
            result = f"🤝 Ничья\n↩️ **{format_num(bet)}** VC"
        else:
            await db.update_stats(callback.from_user.id, False, bet)
            result = f"❌ Проигрыш\n💔 **-{format_num(bet)}** VC"

        await callback.message.edit_text(
            f"🃏 **БЛЕКДЖЕК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Ты: {Blackjack.pretty(player)} (**{player_val}**)\n"
            f"🤖 Дилер: {Blackjack.pretty(dealer)} (**{dealer_val}**)\n\n"
            f"{result}"
        )
