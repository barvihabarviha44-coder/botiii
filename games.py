import random
import asyncio
import json
from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from utils import format_num, parse_amount, maybe_give_xp

games_router = Router()


# ==================== МИНЫ ====================

class MinesGame:
    @staticmethod
    def calculate_multiplier(opened: int, mines_count: int) -> float:
        multipliers = {
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
        return multipliers.get(opened, {}).get(mines_count, 1.0)
    
    @staticmethod
    def create_keyboard(session_id: int, opened: list, mines: list, game_over: bool = False):
        keyboard = []
        for row in range(5):
            row_buttons = []
            for col in range(5):
                cell = row * 5 + col
                if game_over:
                    text = "💣" if cell in mines else ("💎" if cell in opened else "⬜")
                    callback = "disabled"
                elif cell in opened:
                    text = "💎"
                    callback = "disabled"
                else:
                    text = "🟦"
                    callback = f"mines_{session_id}_{cell}"
                row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback))
            keyboard.append(row_buttons)
        return keyboard


@games_router.message(lambda m: m.text and m.text.lower().startswith('мины'))
async def mines_start(message: Message):
    text = message.text.lower().replace('мины', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ Что это?", callback_data="info_mines")]
        ])
        await message.answer(
            "💣 **МИНЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎮 `мины [ставка] [мины 1-6]`\n\n"
            "📝 Пример: `мины 100к 5`",
            reply_markup=keyboard
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[0], user['coins'])
    mines_count = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= 6 else 3
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    xp = maybe_give_xp()
    if xp > 0:
        await db.add_xp(message.from_user.id, xp)
    
    mines = random.sample(range(25), mines_count)
    state = {'mines': mines, 'opened': [], 'mines_count': mines_count, 'bet': bet}
    session_id = await db.create_game_session(message.from_user.id, 'mines', bet, state)
    
    keyboard_rows = MinesGame.create_keyboard(session_id, [], mines, False)
    keyboard_rows.append([InlineKeyboardButton(text="🎲 Случайно", callback_data=f"mines_random_{session_id}")])
    
    await message.answer(
        f"💣 **МИНЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n"
        f"💣 Мин: **{mines_count}** | 📈 x**1.00**\n\n"
        f"🎯 Выбери ячейку!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    )


@games_router.callback_query(lambda c: c.data.startswith('mines_'))
async def mines_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    
    if parts[1] == "random":
        session_id = int(parts[2])
        session = await db.get_game_session(callback.from_user.id, 'mines')
        if not session or session['id'] != session_id or not session['is_active']:
            await callback.answer("❌ Игра не найдена!", show_alert=True)
            return
        
        state = json.loads(session['state'])
        available = [i for i in range(25) if i not in state['opened'] and i not in state['mines']]
        if not available:
            await callback.answer("❌ Нет ячеек!", show_alert=True)
            return
        
        cell = random.choice(available)
        state['opened'].append(cell)
        mult = MinesGame.calculate_multiplier(len(state['opened']), state['mines_count'])
        await db.update_game_session(session_id, state, True)
        
        keyboard_rows = MinesGame.create_keyboard(session_id, state['opened'], state['mines'], False)
        win = int(state['bet'] * mult)
        keyboard_rows.append([InlineKeyboardButton(text=f"💰 Забрать {format_num(win)}", callback_data=f"mines_cashout_{session_id}")])
        keyboard_rows.append([InlineKeyboardButton(text="🎲 Случайно", callback_data=f"mines_random_{session_id}")])
        
        await callback.message.edit_text(
            f"💣 **МИНЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 **{format_num(state['bet'])}** VC | 📈 x**{mult:.2f}**\n"
            f"💵 Забрать: **{format_num(win)}** VC",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        )
        await callback.answer("✅ Безопасно!")
        return
    
    if parts[1] == "cashout":
        session_id = int(parts[2])
        session = await db.get_game_session(callback.from_user.id, 'mines')
        if not session or session['id'] != session_id or not session['is_active']:
            await callback.answer("❌ Игра не найдена!", show_alert=True)
            return
        
        state = json.loads(session['state'])
        if len(state['opened']) == 0:
            await callback.answer("❌ Открой хотя бы 1 ячейку!", show_alert=True)
            return
        
        mult = MinesGame.calculate_multiplier(len(state['opened']), state['mines_count'])
        win = int(state['bet'] * mult)
        
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await db.close_game_session(session_id)
        
        keyboard_rows = MinesGame.create_keyboard(session_id, state['opened'], state['mines'], True)
        
        await callback.message.edit_text(
            f"💣 **МИНЫ — ПОБЕДА!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Открыто: **{len(state['opened'])}** | 📈 x**{mult:.2f}**\n\n"
            f"🏆 **+{format_num(win)}** VC",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        )
        return
    
    session_id = int(parts[1])
    cell = int(parts[2])
    
    session = await db.get_game_session(callback.from_user.id, 'mines')
    if not session or session['id'] != session_id or not session['is_active']:
        await callback.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    state = json.loads(session['state'])
    
    if cell in state['mines']:
        await db.update_stats(callback.from_user.id, False, state['bet'])
        await db.close_game_session(session_id)
        state['opened'].append(cell)
        
        keyboard_rows = MinesGame.create_keyboard(session_id, state['opened'], state['mines'], True)
        
        await callback.message.edit_text(
            f"💣 **МИНЫ — ВЗРЫВ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💥 Попал на мину!\n\n"
            f"💔 **-{format_num(state['bet'])}** VC",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        )
        await callback.answer("💥 ВЗРЫВ!", show_alert=True)
        return
    
    state['opened'].append(cell)
    mult = MinesGame.calculate_multiplier(len(state['opened']), state['mines_count'])
    
    if len(state['opened']) >= (25 - state['mines_count']):
        win = int(state['bet'] * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await db.close_game_session(session_id)
        
        keyboard_rows = MinesGame.create_keyboard(session_id, state['opened'], state['mines'], True)
        
        await callback.message.edit_text(
            f"💣 **МИНЫ — ДЖЕКПОТ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎉 Все ячейки!\n\n"
            f"🏆 **+{format_num(win)}** VC",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        )
        return
    
    await db.update_game_session(session_id, state, True)
    
    keyboard_rows = MinesGame.create_keyboard(session_id, state['opened'], state['mines'], False)
    win = int(state['bet'] * mult)
    keyboard_rows.append([InlineKeyboardButton(text=f"💰 Забрать {format_num(win)}", callback_data=f"mines_cashout_{session_id}")])
    keyboard_rows.append([InlineKeyboardButton(text="🎲 Случайно", callback_data=f"mines_random_{session_id}")])
    
    await callback.message.edit_text(
        f"💣 **МИНЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 **{format_num(state['bet'])}** VC | 📈 x**{mult:.2f}**\n"
        f"💵 Забрать: **{format_num(win)}** VC",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    )
    await callback.answer("✅ Безопасно!")


# ==================== АЛМАЗЫ ====================

class DiamondsGame:
    @staticmethod
    def get_multiplier(level: int, difficulty: int) -> float:
        if difficulty == 1:
            mults = {1: 1.08, 2: 1.17, 3: 1.27, 4: 1.38, 5: 1.50, 6: 1.63, 7: 1.77, 8: 1.92, 9: 2.09, 10: 2.27, 11: 2.47, 12: 2.68, 13: 2.92, 14: 3.17, 15: 3.45, 16: 3.75}
        else:
            mults = {1: 1.13, 2: 1.28, 3: 1.45, 4: 1.64, 5: 1.86, 6: 2.11, 7: 2.39, 8: 2.71, 9: 3.07, 10: 3.48, 11: 3.95, 12: 4.48, 13: 5.08, 14: 5.76, 15: 6.53, 16: 7.41}
        return mults.get(level, 1.0)
    
    @staticmethod
    def create_keyboard(session_id: int, size: int, diamond_pos: int, game_over: bool = False, chosen: int = -1):
        keyboard = []
        for row in range(size):
            row_buttons = []
            for col in range(size):
                cell = row * size + col
                if game_over:
                    text = "💎" if cell == diamond_pos else ("❌" if cell == chosen else "⬜")
                    callback = "disabled"
                else:
                    text = "🟦"
                    callback = f"diamond_{session_id}_{cell}"
                row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback))
            keyboard.append(row_buttons)
        return keyboard


@games_router.message(lambda m: m.text and m.text.lower().startswith('алмаз'))
async def diamond_start(message: Message):
    text = message.text.lower().replace('алмазы', '').replace('алмаз', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ Что это?", callback_data="info_diamond")]
        ])
        await message.answer(
            "💎 **АЛМАЗЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎮 `алмазы [ставка] [сложность 1-2]`\n\n"
            "📝 Пример: `алмазы 100к 2`",
            reply_markup=keyboard
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[0], user['coins'])
    difficulty = int(parts[1]) if len(parts) >= 2 and parts[1] in ['1', '2'] else 1
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    xp = maybe_give_xp()
    if xp > 0:
        await db.add_xp(message.from_user.id, xp)
    
    size = 3 if difficulty == 1 else 4
    diamond_pos = random.randint(0, size * size - 1)
    state = {'level': 1, 'difficulty': difficulty, 'bet': bet, 'size': size, 'diamond_pos': diamond_pos}
    session_id = await db.create_game_session(message.from_user.id, 'diamonds', bet, state)
    
    keyboard_rows = DiamondsGame.create_keyboard(session_id, size, diamond_pos, False)
    mult = DiamondsGame.get_multiplier(1, difficulty)
    
    await message.answer(
        f"💎 **АЛМАЗЫ** — Уровень 1/16\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 **{format_num(bet)}** VC | 📈 x**{mult:.2f}**\n\n"
        f"🔍 Найди алмаз!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    )


@games_router.callback_query(lambda c: c.data.startswith('diamond_'))
async def diamond_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    
    if parts[1] == "cashout":
        session_id = int(parts[2])
        session = await db.get_game_session(callback.from_user.id, 'diamonds')
        if not session or session['id'] != session_id or not session['is_active']:
            await callback.answer("❌ Игра не найдена!", show_alert=True)
            return
        
        state = json.loads(session['state'])
        if state['level'] <= 1:
            await callback.answer("❌ Пройди хотя бы 1 уровень!", show_alert=True)
            return
        
        mult = DiamondsGame.get_multiplier(state['level'] - 1, state['difficulty'])
        win = int(state['bet'] * mult)
        
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await db.close_game_session(session_id)
        
        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ — ЗАБРАЛ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Уровней: **{state['level'] - 1}** | 📈 x**{mult:.2f}**\n\n"
            f"🏆 **+{format_num(win)}** VC"
        )
        return
    
    session_id = int(parts[1])
    cell = int(parts[2])
    
    session = await db.get_game_session(callback.from_user.id, 'diamonds')
    if not session or session['id'] != session_id or not session['is_active']:
        await callback.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    state = json.loads(session['state'])
    
    if cell != state['diamond_pos']:
        await db.update_stats(callback.from_user.id, False, state['bet'])
        await db.close_game_session(session_id)
        
        keyboard_rows = DiamondsGame.create_keyboard(session_id, state['size'], state['diamond_pos'], True, cell)
        
        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ — ПРОИГРЫШ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"❌ Не угадал!\n\n"
            f"💔 **-{format_num(state['bet'])}** VC",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        )
        await callback.answer("❌ Не угадал!", show_alert=True)
        return
    
    state['level'] += 1
    
    if state['level'] > 16:
        mult = DiamondsGame.get_multiplier(16, state['difficulty'])
        win = int(state['bet'] * mult)
        
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await db.close_game_session(session_id)
        
        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ — ДЖЕКПОТ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎉 Все 16 уровней!\n\n"
            f"🏆 **+{format_num(win)}** VC"
        )
        return
    
    state['size'] = 3 if state['difficulty'] == 1 else 4
    state['diamond_pos'] = random.randint(0, state['size'] * state['size'] - 1)
    await db.update_game_session(session_id, state, True)
    
    keyboard_rows = DiamondsGame.create_keyboard(session_id, state['size'], state['diamond_pos'], False)
    prev_mult = DiamondsGame.get_multiplier(state['level'] - 1, state['difficulty'])
    prev_win = int(state['bet'] * prev_mult)
    keyboard_rows.append([InlineKeyboardButton(text=f"💰 Забрать {format_num(prev_win)}", callback_data=f"diamond_cashout_{session_id}")])
    
    curr_mult = DiamondsGame.get_multiplier(state['level'], state['difficulty'])
    
    await callback.message.edit_text(
        f"💎 **АЛМАЗЫ** — Уровень {state['level']}/16\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Угадал! 📈 x**{curr_mult:.2f}**\n\n"
        f"🔍 Найди алмаз!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    )
    await callback.answer("✅ Угадал!")


# ==================== РУЛЕТКА ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('рулетка'))
async def roulette_start(message: Message):
    text = message.text.lower().replace('рулетка', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ Что это?", callback_data="info_roulette")]
        ])
        await message.answer(
            "🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎮 `рулетка [ставка]`\n\n"
            "📝 Пример: `рулетка 100к`",
            reply_markup=keyboard
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[0], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Красное x2", callback_data=f"rlt_{bet}_red"),
            InlineKeyboardButton(text="⚫ Чёрное x2", callback_data=f"rlt_{bet}_black"),
        ],
        [InlineKeyboardButton(text="🟢 Зеро x36", callback_data=f"rlt_{bet}_zero")],
        [
            InlineKeyboardButton(text="1-12 x3", callback_data=f"rlt_{bet}_1-12"),
            InlineKeyboardButton(text="13-24 x3", callback_data=f"rlt_{bet}_13-24"),
            InlineKeyboardButton(text="25-36 x3", callback_data=f"rlt_{bet}_25-36"),
        ]
    ])
    
    await message.answer(
        f"🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC\n\n"
        f"🎯 Выбери ставку:",
        reply_markup=keyboard
    )


@games_router.callback_query(lambda c: c.data.startswith('rlt_'))
async def roulette_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet = int(parts[1])
    choice = parts[2]
    
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Нет денег!", show_alert=True)
        return
    
    await db.update_coins(callback.from_user.id, -bet)
    
    xp = maybe_give_xp()
    if xp > 0:
        await db.add_xp(callback.from_user.id, xp)
    
    await callback.message.edit_text("🎡 **РУЛЕТКА**\n\n🎰 Крутим...")
    await asyncio.sleep(2)
    
    result = random.randint(0, 36)
    RED = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    
    color = "🟢" if result == 0 else ("🔴" if result in RED else "⚫")
    
    won, mult = False, 0
    if choice == "red" and result in RED: won, mult = True, 2
    elif choice == "black" and result not in RED and result != 0: won, mult = True, 2
    elif choice == "zero" and result == 0: won, mult = True, 36
    elif choice == "1-12" and 1 <= result <= 12: won, mult = True, 3
    elif choice == "13-24" and 13 <= result <= 24: won, mult = True, 3
    elif choice == "25-36" and 25 <= result <= 36: won, mult = True, 3
    
    if won:
        win = bet * mult
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.edit_text(f"🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n{color} Выпало: **{result}**\n\n✅ x{mult} | 🏆 **+{format_num(win)}** VC")
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.edit_text(f"🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n{color} Выпало: **{result}**\n\n❌ **-{format_num(bet)}** VC")


# ==================== КРАШ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('краш'))
async def crash_start(message: Message):
    text = message.text.lower().replace('краш', '').strip()
    parts = text.split()
    
    if len(parts) < 2:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ Что это?", callback_data="info_crash")]
        ])
        await message.answer(
            "📈 **КРАШ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎮 `краш [ставка] [вывод]`\n\n"
            "📝 Пример: `краш 100к 2.5`",
            reply_markup=keyboard
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[0], user['coins'])
    try:
        cashout = float(parts[1].replace('x', '').replace(',', '.'))
    except:
        await message.answer("❌ Некорректный множитель!")
        return
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    if cashout < 1.01 or cashout > 505:
        await message.answer("❌ Множитель: 1.01 - 505!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    xp = maybe_give_xp()
    if xp > 0:
        await db.add_xp(message.from_user.id, xp)
    
    r = random.random()
    if r < 0.4: crash_point = round(random.uniform(1.0, 1.5), 2)
    elif r < 0.7: crash_point = round(random.uniform(1.5, 3.0), 2)
    elif r < 0.9: crash_point = round(random.uniform(3.0, 10.0), 2)
    else: crash_point = round(random.uniform(10.0, 100.0), 2)
    
    msg = await message.answer(f"📈 **КРАШ**\n━━━━━━━━━━━━━━━━━━━━\n\n💰 **{format_num(bet)}** VC → x**{cashout}**\n\n🚀 x**1.00**")
    
    current = 1.0
    step = 0.05
    while current < min(crash_point, cashout + 0.3):
        current = round(current + step, 2)
        step *= 1.08
        if current >= crash_point: break
        if current >= cashout: break
        bar_len = min(int((current / cashout) * 15), 15)
        bar = "█" * bar_len + "░" * (15 - bar_len)
        try:
            await msg.edit_text(f"📈 **КРАШ**\n━━━━━━━━━━━━━━━━━━━━\n\n💰 **{format_num(bet)}** → x**{cashout}**\n\n🚀 x**{current}**\n[{bar}]")
        except: pass
        await asyncio.sleep(0.25)
    
    if cashout <= crash_point:
        win = int(bet * cashout)
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await msg.edit_text(f"📈 **КРАШ — УСПЕХ!**\n━━━━━━━━━━━━━━━━━━━━\n\n✅ x**{cashout}** | 💥 x**{crash_point}**\n\n🏆 **+{format_num(win)}** VC")
    else:
        await db.update_stats(message.from_user.id, False, bet)
        await msg.edit_text(f"📈 **КРАШ — КРАХ!**\n━━━━━━━━━━━━━━━━━━━━\n\n💥 x**{crash_point}** | 🎯 x**{cashout}**\n\n💔 **-{format_num(bet)}** VC")


# ==================== КОСТИ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('кости'))
async def dice_start(message: Message):
    text = message.text.lower().replace('кости', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ Что это?", callback_data="info_dice")]
        ])
        await message.answer("🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎮 `кости [ставка]`\n\n📝 Пример: `кости 100к`", reply_markup=keyboard)
        return
    
    user = await db.get_user(message.from_user.id)
    if not user: return
    
    bet = parse_amount(parts[0], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Больше 7 (x2.3)", callback_data=f"dice_{bet}_more"), InlineKeyboardButton(text="📉 Меньше 7 (x2.3)", callback_data=f"dice_{bet}_less")],
        [InlineKeyboardButton(text="🎯 Ровно 7 (x5.8)", callback_data=f"dice_{bet}_exact")]
    ])
    
    await message.answer(f"🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n💰 Ставка: **{format_num(bet)}** VC\n\n🎯 Угадай сумму:", reply_markup=keyboard)


@games_router.callback_query(lambda c: c.data.startswith('dice_'))
async def dice_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet = int(parts[1])
    choice = parts[2]
    
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Нет денег!", show_alert=True)
        return
    
    await db.update_coins(callback.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp > 0: await db.add_xp(callback.from_user.id, xp)
    
    await callback.message.edit_text("🎲 **КОСТИ**\n\n🎰 Бросаем...")
    d1 = await callback.message.answer_dice(emoji="🎲")
    await asyncio.sleep(0.5)
    d2 = await callback.message.answer_dice(emoji="🎲")
    await asyncio.sleep(4)
    
    total = d1.dice.value + d2.dice.value
    
    won, mult = False, 0
    if choice == "more" and total > 7: won, mult = True, 2.3
    elif choice == "less" and total < 7: won, mult = True, 2.3
    elif choice == "exact" and total == 7: won, mult = True, 5.8
    
    if won:
        win = int(bet * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.answer(f"🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Сумма: **{total}**\n\n✅ x{mult} | 🏆 **+{format_num(win)}** VC")
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.answer(f"🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Сумма: **{total}**\n\n❌ **-{format_num(bet)}** VC")


# ==================== ФУТБОЛ, БАСКЕТБОЛ, БОУЛИНГ, ДАРТС ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('футбол'))
async def football_start(message: Message):
    parts = message.text.lower().replace('футбол', '').strip().split()
    if len(parts) < 1:
        await message.answer("⚽ **ФУТБОЛ**\n\n🎮 `футбол [ставка]`", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❓ Что это?", callback_data="info_football")]]))
        return
    user = await db.get_user(message.from_user.id)
    if not user: return
    bet = parse_amount(parts[0], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚽ Гол (x1.8)", callback_data=f"foot_{bet}_goal"), InlineKeyboardButton(text="❌ Мимо (x3.7)", callback_data=f"foot_{bet}_miss")]])
    await message.answer(f"⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n💰 **{format_num(bet)}** VC\n\n🎯 Угадай:", reply_markup=keyboard)


@games_router.callback_query(lambda c: c.data.startswith('foot_'))
async def football_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet, choice = int(parts[1]), parts[2]
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Нет денег!", show_alert=True)
        return
    await db.update_coins(callback.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp > 0: await db.add_xp(callback.from_user.id, xp)
    await callback.message.edit_text("⚽ **ФУТБОЛ**\n\n🏃 Удар...")
    dice = await callback.message.answer_dice(emoji="⚽")
    await asyncio.sleep(4)
    is_goal = dice.dice.value >= 3
    won = (choice == "goal" and is_goal) or (choice == "miss" and not is_goal)
    mult = 1.8 if choice == "goal" else 3.7
    result = "⚽ ГОЛ!" if is_goal else "❌ Мимо!"
    if won:
        win = int(bet * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.answer(f"⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n{result}\n\n✅ x{mult} | 🏆 **+{format_num(win)}** VC")
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.answer(f"⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n{result}\n\n❌ **-{format_num(bet)}** VC")


@games_router.message(lambda m: m.text and m.text.lower().startswith('баскетбол'))
async def basketball_start(message: Message):
    parts = message.text.lower().replace('баскетбол', '').strip().split()
    if len(parts) < 1:
        await message.answer("🏀 **БАСКЕТБОЛ**\n\n🎮 `баскетбол [ставка]`", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❓ Что это?", callback_data="info_basketball")]]))
        return
    user = await db.get_user(message.from_user.id)
    if not user: return
    bet = parse_amount(parts[0], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏀 Попал (x3.8)", callback_data=f"bask_{bet}_goal"), InlineKeyboardButton(text="❌ Мимо (x1.9)", callback_data=f"bask_{bet}_miss")]])
    await message.answer(f"🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n💰 **{format_num(bet)}** VC\n\n🎯 Угадай:", reply_markup=keyboard)


@games_router.callback_query(lambda c: c.data.startswith('bask_'))
async def basketball_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet, choice = int(parts[1]), parts[2]
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Нет денег!", show_alert=True)
        return
    await db.update_coins(callback.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp > 0: await db.add_xp(callback.from_user.id, xp)
    await callback.message.edit_text("🏀 **БАСКЕТБОЛ**\n\n🏃 Бросок...")
    dice = await callback.message.answer_dice(emoji="🏀")
    await asyncio.sleep(4)
    is_goal = dice.dice.value >= 4
    won = (choice == "goal" and is_goal) or (choice == "miss" and not is_goal)
    mult = 3.8 if choice == "goal" else 1.9
    result = "🏀 Попал!" if is_goal else "❌ Мимо!"
    if won:
        win = int(bet * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.answer(f"🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n{result}\n\n✅ x{mult} | 🏆 **+{format_num(win)}** VC")
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.answer(f"🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n{result}\n\n❌ **-{format_num(bet)}** VC")


@games_router.message(lambda m: m.text and m.text.lower().startswith('дартс'))
async def darts_start(message: Message):
    parts = message.text.lower().replace('дартс', '').strip().split()
    if len(parts) < 1:
        await message.answer("🎯 **ДАРТС**\n\n🎮 `дартс [ставка]`", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❓ Что это?", callback_data="info_darts")]]))
        return
    user = await db.get_user(message.from_user.id)
    if not user: return
    bet = parse_amount(parts[0], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Центр (x5.8)", callback_data=f"dart_{bet}_center"), InlineKeyboardButton(text="❌ Мимо (x5.8)", callback_data=f"dart_{bet}_miss")],
        [InlineKeyboardButton(text="⚪ Белое (x1.9)", callback_data=f"dart_{bet}_white"), InlineKeyboardButton(text="🔴 Красное (x1.9)", callback_data=f"dart_{bet}_red")]
    ])
    await message.answer(f"🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n💰 **{format_num(bet)}** VC\n\n🎯 Угадай:", reply_markup=keyboard)


@games_router.callback_query(lambda c: c.data.startswith('dart_'))
async def darts_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet, choice = int(parts[1]), parts[2]
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Нет денег!", show_alert=True)
        return
    await db.update_coins(callback.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp > 0: await db.add_xp(callback.from_user.id, xp)
    await callback.message.edit_text("🎯 **ДАРТС**\n\n🏹 Бросок...")
    dice = await callback.message.answer_dice(emoji="🎯")
    await asyncio.sleep(4)
    v = dice.dice.value
    result_map = {1: "miss", 2: "white", 3: "white", 4: "red", 5: "red", 6: "center"}
    result = result_map[v]
    result_text = {"center": "🎯 Центр!", "miss": "❌ Мимо!", "white": "⚪ Белое", "red": "🔴 Красное"}[result]
    mult = {"center": 5.8, "miss": 5.8, "white": 1.9, "red": 1.9}[choice]
    won = choice == result
    if won:
        win = int(bet * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.answer(f"🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n{result_text}\n\n✅ x{mult} | 🏆 **+{format_num(win)}** VC")
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.answer(f"🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n{result_text}\n\n❌ **-{format_num(bet)}** VC")


@games_router.message(lambda m: m.text and m.text.lower().startswith('боулинг'))
async def bowling_start(message: Message):
    parts = message.text.lower().replace('боулинг', '').strip().split()
    if len(parts) < 1:
        await message.answer("🎳 **БОУЛИНГ**\n\n🎮 `боулинг [ставка]`", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❓ Что это?", callback_data="info_bowling")]]))
        return
    user = await db.get_user(message.from_user.id)
    if not user: return
    bet = parse_amount(parts[0], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎳 Страйк (x5.3)", callback_data=f"bowl_{bet}_strike"), InlineKeyboardButton(text="❌ Мимо (x5.3)", callback_data=f"bowl_{bet}_miss")],
        [InlineKeyboardButton(text="1-3 (x1.9)", callback_data=f"bowl_{bet}_1-3"), InlineKeyboardButton(text="4-5 (x1.9)", callback_data=f"bowl_{bet}_4-5")]
    ])
    await message.answer(f"🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n💰 **{format_num(bet)}** VC\n\n🎯 Угадай:", reply_markup=keyboard)


@games_router.callback_query(lambda c: c.data.startswith('bowl_'))
async def bowling_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet, choice = int(parts[1]), parts[2]
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Нет денег!", show_alert=True)
        return
    await db.update_coins(callback.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp > 0: await db.add_xp(callback.from_user.id, xp)
    await callback.message.edit_text("🎳 **БОУЛИНГ**\n\n🎳 Бросок...")
    dice = await callback.message.answer_dice(emoji="🎳")
    await asyncio.sleep(4)
    v = dice.dice.value
    result_map = {1: "miss", 2: "1-3", 3: "1-3", 4: "4-5", 5: "4-5", 6: "strike"}
    result = result_map[v]
    result_text = {"strike": "🎳 СТРАЙК!", "miss": "❌ Мимо!", "1-3": f"🎳 {v} кегли", "4-5": f"🎳 {v} кеглей"}[result]
    mult = {"strike": 5.3, "miss": 5.3, "1-3": 1.9, "4-5": 1.9}[choice]
    won = choice == result
    if won:
        win = int(bet * mult)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        await callback.message.answer(f"🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n{result_text}\n\n✅ x{mult} | 🏆 **+{format_num(win)}** VC")
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        await callback.message.answer(f"🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n{result_text}\n\n❌ **-{format_num(bet)}** VC")


# ==================== СЛОТЫ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('слот'))
async def slots_start(message: Message):
    parts = message.text.lower().replace('слоты', '').replace('слот', '').strip().split()
    
    if len(parts) < 1:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ Что это?", callback_data="info_slots")]
        ])
        await message.answer("🎰 **СЛОТЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎮 `слоты [ставка]`\n\n📝 Пример: `слоты 100к`", reply_markup=keyboard)
        return
    
    user = await db.get_user(message.from_user.id)
    if not user: return
    
    bet = parse_amount(parts[0], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp > 0: await db.add_xp(message.from_user.id, xp)
    
    await message.answer("🎰 **СЛОТЫ**\n\n🎲 Крутим барабаны...")
    
    dice = await message.answer_dice(emoji="🎰")
    await asyncio.sleep(3)
    
    value = dice.dice.value
    # Телеграм слоты: 1-64
    # 1, 22, 43 = 777 (bar-bar-bar)
    # 16, 32, 48, 64 = три одинаковых
    
    win = 0
    result_text = ""
    
    if value in [1, 22, 43]:  # 777
        win = bet * 50
        result_text = "🎰 **777 — ДЖЕКПОТ!**"
    elif value == 64:  # Три 7
        win = bet * 50
        result_text = "🎰 **777 — ДЖЕКПОТ!**"
    elif value in [16, 32, 48]:  # Три одинаковых
        win = bet * 10
        result_text = "🎰 **Три одинаковых!**"
    elif value in [2, 3, 4, 17, 18, 33, 34, 49, 50]:  # Два одинаковых
        win = bet * 2
        result_text = "🎰 Два совпадения"
    else:
        result_text = "🎰 Нет совпадений"
    
    if win > 0:
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await message.answer(f"🎰 **СЛОТЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n{result_text}\n\n🏆 **+{format_num(win)}** VC")
    else:
        await db.update_stats(message.from_user.id, False, bet)
        await message.answer(f"🎰 **СЛОТЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n{result_text}\n\n❌ **-{format_num(bet)}** VC")


# ==================== БЛЕКДЖЕК ====================

class BlackjackGame:
    CARDS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    
    @staticmethod
    def card_value(card: str, current_sum: int) -> int:
        if card in ['J', 'Q', 'K']:
            return 10
        elif card == 'A':
            return 11 if current_sum + 11 <= 21 else 1
        else:
            return int(card)
    
    @staticmethod
    def hand_value(hand: list) -> int:
        value = 0
        aces = 0
        for card in hand:
            if card == 'A':
                aces += 1
            elif card in ['J', 'Q', 'K']:
                value += 10
            else:
                value += int(card)
        for _ in range(aces):
            if value + 11 <= 21:
                value += 11
            else:
                value += 1
        return value
    
    @staticmethod
    def draw_card(deck: list) -> str:
        return deck.pop(random.randint(0, len(deck) - 1))
    
    @staticmethod
    def format_hand(hand: list) -> str:
        cards_emoji = {'2': '2️⃣', '3': '3️⃣', '4': '4️⃣', '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣', '10': '🔟', 'J': '🃏', 'Q': '👸', 'K': '🤴', 'A': '🅰️'}
        return ' '.join([cards_emoji.get(c, c) for c in hand])


@games_router.message(lambda m: m.text and (m.text.lower().startswith('блекджек') or m.text.lower().startswith('бд') or m.text.lower().startswith('blackjack')))
async def blackjack_start(message: Message):
    text = message.text.lower()
    for prefix in ['блекджек', 'blackjack', 'бд']:
        text = text.replace(prefix, '')
    parts = text.strip().split()
    
    if len(parts) < 1:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ Что это?", callback_data="info_blackjack")]
        ])
        await message.answer("🃏 **БЛЕКДЖЕК**\n━━━━━━━━━━━━━━━━━━━━\n\n🎮 `бд [ставка]`\n\n📝 Пример: `бд 100к`", reply_markup=keyboard)
        return
    
    user = await db.get_user(message.from_user.id)
    if not user: return
    
    bet = parse_amount(parts[0], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    xp = maybe_give_xp()
    if xp > 0: await db.add_xp(message.from_user.id, xp)
    
    # Создаем колоду
    deck = BlackjackGame.CARDS * 4
    random.shuffle(deck)
    
    player_hand = [BlackjackGame.draw_card(deck), BlackjackGame.draw_card(deck)]
    dealer_hand = [BlackjackGame.draw_card(deck), BlackjackGame.draw_card(deck)]
    
    player_value = BlackjackGame.hand_value(player_hand)
    
    state = {'deck': deck, 'player': player_hand, 'dealer': dealer_hand, 'bet': bet}
    session_id = await db.create_game_session(message.from_user.id, 'blackjack', bet, state)
    
    # Блекджек с раздачи
    if player_value == 21:
        dealer_value = BlackjackGame.hand_value(dealer_hand)
        await db.close_game_session(session_id)
        
        if dealer_value == 21:
            await db.update_coins(message.from_user.id, bet)
            await message.answer(f"🃏 **БЛЕКДЖЕК**\n━━━━━━━━━━━━━━━━━━━━\n\n👤 {BlackjackGame.format_hand(player_hand)} = **21**\n🤖 {BlackjackGame.format_hand(dealer_hand)} = **21**\n\n🤝 Ничья!")
        else:
            win = int(bet * 2.5)
            await db.update_coins(message.from_user.id, win)
            await db.update_stats(message.from_user.id, True, win)
            await message.answer(f"🃏 **БЛЕКДЖЕК!**\n━━━━━━━━━━━━━━━━━━━━\n\n👤 {BlackjackGame.format_hand(player_hand)} = **21** 🎉\n\n🏆 **+{format_num(win)}** VC")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Ещё карту", callback_data=f"bj_hit_{session_id}"), InlineKeyboardButton(text="✋ Хватит", callback_data=f"bj_stand_{session_id}")]
    ])
    
    await message.answer(
        f"🃏 **БЛЕКДЖЕК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Ты: {BlackjackGame.format_hand(player_hand)} = **{player_value}**\n"
        f"🤖 Дилер: {dealer_hand[0]} ❓\n\n"
        f"💰 Ставка: **{format_num(bet)}** VC",
        reply_markup=keyboard
    )


@games_router.callback_query(lambda c: c.data.startswith('bj_'))
async def blackjack_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    action = parts[1]
    session_id = int(parts[2])
    
    session = await db.get_game_session(callback.from_user.id, 'blackjack')
    if not session or session['id'] != session_id or not session['is_active']:
        await callback.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    state = json.loads(session['state'])
    
    if action == "hit":
        state['player'].append(BlackjackGame.draw_card(state['deck']))
        player_value = BlackjackGame.hand_value(state['player'])
        
        if player_value > 21:
            await db.update_stats(callback.from_user.id, False, state['bet'])
            await db.close_game_session(session_id)
            
            await callback.message.edit_text(
                f"🃏 **БЛЕКДЖЕК — ПЕРЕБОР!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 {BlackjackGame.format_hand(state['player'])} = **{player_value}** 💥\n\n"
                f"❌ **-{format_num(state['bet'])}** VC"
            )
            return
        
        if player_value == 21:
            action = "stand"
        else:
            await db.update_game_session(session_id, state, True)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📥 Ещё", callback_data=f"bj_hit_{session_id}"), InlineKeyboardButton(text="✋ Хватит", callback_data=f"bj_stand_{session_id}")]
            ])
            
            await callback.message.edit_text(
                f"🃏 **БЛЕКДЖЕК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 Ты: {BlackjackGame.format_hand(state['player'])} = **{player_value}**\n"
                f"🤖 Дилер: {state['dealer'][0]} ❓",
                reply_markup=keyboard
            )
            return
    
    if action == "stand":
        player_value = BlackjackGame.hand_value(state['player'])
        dealer_value = BlackjackGame.hand_value(state['dealer'])
        
        # Дилер добирает до 17
        while dealer_value < 17:
            state['dealer'].append(BlackjackGame.draw_card(state['deck']))
            dealer_value = BlackjackGame.hand_value(state['dealer'])
        
        await db.close_game_session(session_id)
        
        if dealer_value > 21:
            win = state['bet'] * 2
            await db.update_coins(callback.from_user.id, win)
            await db.update_stats(callback.from_user.id, True, win)
            result = f"🤖 Перебор!\n\n🏆 **+{format_num(win)}** VC"
        elif player_value > dealer_value:
            win = state['bet'] * 2
            await db.update_coins(callback.from_user.id, win)
            await db.update_stats(callback.from_user.id, True, win)
            result = f"✅ Победа!\n\n🏆 **+{format_num(win)}** VC"
        elif player_value < dealer_value:
            await db.update_stats(callback.from_user.id, False, state['bet'])
            result = f"❌ Проигрыш\n\n💔 **-{format_num(state['bet'])}** VC"
        else:
            await db.update_coins(callback.from_user.id, state['bet'])
            result = "🤝 Ничья!"
        
        await callback.message.edit_text(
            f"🃏 **БЛЕКДЖЕК**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Ты: {BlackjackGame.format_hand(state['player'])} = **{player_value}**\n"
            f"🤖 Дилер: {BlackjackGame.format_hand(state['dealer'])} = **{dealer_value}**\n\n"
            f"{result}"
        )


# ==================== INFO CALLBACKS ====================

@games_router.callback_query(lambda c: c.data.startswith('info_'))
async def info_callback(callback: CallbackQuery):
    game = callback.data.replace('info_', '')
    
    infos = {
        "mines": "💣 **МИНЫ**\n\nОткрывай ячейки, избегая мин. Чем больше откроешь — тем выше множитель. Забери выигрыш в любой момент!",
        "diamond": "💎 **АЛМАЗЫ**\n\nНайди алмаз на каждом из 16 уровней. Можешь забрать выигрыш после любого уровня.",
        "roulette": "🎡 **РУЛЕТКА**\n\nКлассическая европейская рулетка. Красное/Чёрное x2, Зеро x36, Дюжины x3.",
        "crash": "📈 **КРАШ**\n\nМножитель растёт. Забери до краха! Множитель от 1.01 до 505.",
        "dice": "🎲 **КОСТИ**\n\nУгадай сумму двух кубиков: больше 7, меньше 7 или ровно 7.",
        "football": "⚽ **ФУТБОЛ**\n\nУгадай: гол или мимо. Гол x1.8, Мимо x3.7.",
        "basketball": "🏀 **БАСКЕТБОЛ**\n\nУгадай: попал или мимо. Попал x3.8, Мимо x1.9.",
        "darts": "🎯 **ДАРТС**\n\nУгадай зону попадания: центр, мимо, белое или красное.",
        "bowling": "🎳 **БОУЛИНГ**\n\nУгадай результат: страйк, мимо, 1-3 или 4-5 кеглей.",
        "slots": "🎰 **СЛОТЫ**\n\n777 = x50, три одинаковых = x10, два одинаковых = x2.",
        "blackjack": "🃏 **БЛЕКДЖЕК**\n\nНабери 21 или больше дилера, но не перебери! Блекджек = x2.5."
    }
    
    await callback.answer(infos.get(game, "❓ Нет информации"), show_alert=True)


@games_router.callback_query(lambda c: c.data == 'disabled')
async def disabled_callback(callback: CallbackQuery):
    await callback.answer()
