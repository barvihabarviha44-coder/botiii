import random
import asyncio
import json
from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from utils import format_number, parse_amount

games_router = Router()


# ==================== МИНЫ ====================

class MinesGame:
    """Мины - поле 5x5, от 1 до 6 мин"""
    
    @staticmethod
    def calculate_multiplier(opened: int, mines_count: int) -> float:
        """Расчёт множителя"""
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
        if opened in multipliers and mines_count in multipliers[opened]:
            return multipliers[opened][mines_count]
        return 1.0
    
    @staticmethod
    def create_keyboard(session_id: int, opened: list, mines: list, game_over: bool = False):
        keyboard = []
        for row in range(5):
            row_buttons = []
            for col in range(5):
                cell = row * 5 + col
                if game_over:
                    if cell in mines:
                        text = "💣"
                    elif cell in opened:
                        text = "💎"
                    else:
                        text = "◻️"
                    callback = "game_disabled"
                elif cell in opened:
                    text = "💎"
                    callback = "game_disabled"
                else:
                    text = "◻️"
                    callback = f"mines_{session_id}_{cell}"
                row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback))
            keyboard.append(row_buttons)
        return keyboard


@games_router.message(lambda m: m.text and (m.text.lower().startswith('мины') or m.text.lower().startswith('/mines')))
async def mines_start(message: Message):
    text = message.text.lower().replace('/mines', '').replace('мины', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        await message.answer(
            f"ℹ️ **Мины** — это игра, в которой вам нужно угадать пустые ячейки. "
            f"Чем больше ячеек вы откроете, тем больше получите VC!\n\n"
            f"🤖 Чтобы начать игру, используй команду:\n\n"
            f"💣 `мины [ставка] [мины 1-6]`\n\n"
            f"Пример: `мины 100 6`\n"
            f"Пример: `мины 100`"
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала напиши /start")
        return
    
    bet = parse_amount(parts[0], user['coins'])
    mines_count = 3
    if len(parts) >= 2:
        try:
            mines_count = int(parts[1])
            if mines_count < 1 or mines_count > 6:
                await message.answer("❌ Количество мин: от 1 до 6")
                return
        except:
            pass
    
    if bet <= 0:
        await message.answer("❌ Укажи ставку!")
        return
    if bet > user['coins']:
        await message.answer(f"❌ Недостаточно монет!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    all_cells = list(range(25))
    mines = random.sample(all_cells, mines_count)
    
    state = {'mines': mines, 'opened': [], 'mines_count': mines_count, 'bet': bet}
    session_id = await db.create_game_session(message.from_user.id, 'mines', bet, state)
    
    keyboard_rows = MinesGame.create_keyboard(session_id, [], mines, False)
    keyboard_rows.append([
        InlineKeyboardButton(text="🎲 Случайная ячейка", callback_data=f"mines_random_{session_id}")
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await message.answer(
        f"💣 **МИНЫ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_number(bet)} VC**\n"
        f"💣 Мин: **{mines_count}**\n\n"
        f"✨ Открыто: **0**\n"
        f"📈 Множитель: **x1.00**\n\n"
        f"🎯 Выбери ячейку!",
        reply_markup=keyboard
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
            await callback.answer("❌ Нет доступных ячеек!", show_alert=True)
            return
        
        cell = random.choice(available)
        state['opened'].append(cell)
        opened_count = len(state['opened'])
        mult = MinesGame.calculate_multiplier(opened_count, state['mines_count'])
        
        await db.update_game_session(session_id, state, True)
        
        keyboard_rows = MinesGame.create_keyboard(session_id, state['opened'], state['mines'], False)
        potential_win = int(state['bet'] * mult)
        keyboard_rows.append([
            InlineKeyboardButton(text=f"💰 Забрать {format_number(potential_win)} VC", callback_data=f"mines_cashout_{session_id}")
        ])
        keyboard_rows.append([
            InlineKeyboardButton(text="🎲 Случайная", callback_data=f"mines_random_{session_id}")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        await callback.message.edit_text(
            f"💣 **МИНЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Ставка: **{format_number(state['bet'])} VC**\n"
            f"💣 Мин: **{state['mines_count']}**\n\n"
            f"✨ Открыто: **{opened_count}**\n"
            f"📈 Множитель: **x{mult:.2f}**\n"
            f"💵 Выигрыш: **{format_number(potential_win)} VC**",
            reply_markup=keyboard
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
        opened_count = len(state['opened'])
        
        if opened_count == 0:
            await callback.answer("❌ Сначала открой хотя бы одну ячейку!", show_alert=True)
            return
        
        mult = MinesGame.calculate_multiplier(opened_count, state['mines_count'])
        winnings = int(state['bet'] * mult)
        
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        await db.close_game_session(session_id, "cashout", winnings)
        
        keyboard_rows = MinesGame.create_keyboard(session_id, state['opened'], state['mines'], True)
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        await callback.message.edit_text(
            f"💣 **МИНЫ - ПОБЕДА!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Забрал выигрыш!\n"
            f"✨ Открыто: **{opened_count}** ячеек\n"
            f"📈 Множитель: **x{mult:.2f}**\n\n"
            f"🏆 Выигрыш: **{format_number(winnings)} VC**",
            reply_markup=keyboard
        )
        await callback.answer(f"💰 +{format_number(winnings)} VC!", show_alert=True)
        return
    
    # Открытие ячейки
    session_id = int(parts[1])
    cell = int(parts[2])
    
    session = await db.get_game_session(callback.from_user.id, 'mines')
    if not session or session['id'] != session_id or not session['is_active']:
        await callback.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    state = json.loads(session['state'])
    
    if cell in state['mines']:
        state['opened'].append(cell)
        await db.update_stats(callback.from_user.id, False, state['bet'])
        await db.close_game_session(session_id, "loss", 0)
        
        keyboard_rows = MinesGame.create_keyboard(session_id, state['opened'], state['mines'], True)
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        await callback.message.edit_text(
            f"💣 **МИНЫ - ВЗРЫВ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💥 Попал на мину!\n\n"
            f"💔 Проигрыш: **{format_number(state['bet'])} VC**",
            reply_markup=keyboard
        )
        await callback.answer("💥 ВЗРЫВ!", show_alert=True)
        return
    
    state['opened'].append(cell)
    opened_count = len(state['opened'])
    mult = MinesGame.calculate_multiplier(opened_count, state['mines_count'])
    
    if opened_count >= (25 - state['mines_count']):
        winnings = int(state['bet'] * mult)
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        await db.close_game_session(session_id, "win", winnings)
        
        keyboard_rows = MinesGame.create_keyboard(session_id, state['opened'], state['mines'], True)
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        await callback.message.edit_text(
            f"💣 **МИНЫ - ДЖЕКПОТ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎉 Все ячейки открыты!\n"
            f"📈 Множитель: **x{mult:.2f}**\n\n"
            f"🏆 Выигрыш: **{format_number(winnings)} VC**",
            reply_markup=keyboard
        )
        await callback.answer(f"🎉 ДЖЕКПОТ!", show_alert=True)
        return
    
    await db.update_game_session(session_id, state, True)
    
    keyboard_rows = MinesGame.create_keyboard(session_id, state['opened'], state['mines'], False)
    potential_win = int(state['bet'] * mult)
    keyboard_rows.append([
        InlineKeyboardButton(text=f"💰 Забрать {format_number(potential_win)} VC", callback_data=f"mines_cashout_{session_id}")
    ])
    keyboard_rows.append([
        InlineKeyboardButton(text="🎲 Случайная", callback_data=f"mines_random_{session_id}")
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text(
        f"💣 **МИНЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_number(state['bet'])} VC**\n"
        f"💣 Мин: **{state['mines_count']}**\n\n"
        f"✨ Открыто: **{opened_count}**\n"
        f"📈 Множитель: **x{mult:.2f}**\n"
        f"💵 Выигрыш: **{format_number(potential_win)} VC**",
        reply_markup=keyboard
    )
    await callback.answer("✅ Безопасно!")


# ==================== АЛМАЗЫ ====================

class DiamondsGame:
    @staticmethod
    def get_field_size(level: int, difficulty: int) -> int:
        if difficulty == 1:
            return 3
        else:
            return 4
    
    @staticmethod
    def get_multiplier(level: int, difficulty: int) -> float:
        if difficulty == 1:
            mults = {1: 1.08, 2: 1.17, 3: 1.27, 4: 1.38, 5: 1.50, 6: 1.63, 7: 1.77, 8: 1.92,
                     9: 2.09, 10: 2.27, 11: 2.47, 12: 2.68, 13: 2.92, 14: 3.17, 15: 3.45, 16: 3.75}
        else:
            mults = {1: 1.13, 2: 1.28, 3: 1.45, 4: 1.64, 5: 1.86, 6: 2.11, 7: 2.39, 8: 2.71,
                     9: 3.07, 10: 3.48, 11: 3.95, 12: 4.48, 13: 5.08, 14: 5.76, 15: 6.53, 16: 7.41}
        return mults.get(level, 1.0)
    
    @staticmethod
    def create_keyboard(session_id: int, size: int, diamond_pos: int, game_over: bool = False, chosen: int = -1):
        keyboard = []
        for row in range(size):
            row_buttons = []
            for col in range(size):
                cell = row * size + col
                if game_over:
                    if cell == diamond_pos:
                        text = "💎"
                    elif cell == chosen:
                        text = "❌"
                    else:
                        text = "◻️"
                    callback = "game_disabled"
                else:
                    text = "◻️"
                    callback = f"diamond_{session_id}_{cell}"
                row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback))
            keyboard.append(row_buttons)
        return keyboard


@games_router.message(lambda m: m.text and (m.text.lower().startswith('алмаз') or m.text.lower().startswith('/diamond')))
async def diamond_start(message: Message):
    text = message.text.lower().replace('/diamond', '').replace('алмазы', '').replace('алмаз', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        await message.answer(
            f"ℹ️ **Алмазная лихорадка** — это игра, в которой необходимо угадать, "
            f"в какой ячейке спрятан алмаз. Вам нужно открывать по одной ячейке на "
            f"каждом из 16 уровней, чтобы найти алмаз.\n\n"
            f"🤖 Чтобы начать игру, используй команду:\n\n"
            f"💠 `алмазы [ставка] [сложность 1-2]`\n\n"
            f"Пример: `алмазы 100 2`\n"
            f"Пример: `алмазы 100`"
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала напиши /start")
        return
    
    bet = parse_amount(parts[0], user['coins'])
    difficulty = 1
    if len(parts) >= 2:
        try:
            difficulty = int(parts[1])
            if difficulty < 1 or difficulty > 2:
                await message.answer("❌ Сложность: 1 или 2")
                return
        except:
            pass
    
    if bet <= 0:
        await message.answer("❌ Укажи ставку!")
        return
    if bet > user['coins']:
        await message.answer(f"❌ Недостаточно монет!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    level = 1
    size = DiamondsGame.get_field_size(level, difficulty)
    diamond_pos = random.randint(0, size * size - 1)
    
    state = {'level': level, 'difficulty': difficulty, 'bet': bet, 'size': size, 'diamond_pos': diamond_pos}
    session_id = await db.create_game_session(message.from_user.id, 'diamonds', bet, state)
    
    keyboard_rows = DiamondsGame.create_keyboard(session_id, size, diamond_pos, False)
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    mult = DiamondsGame.get_multiplier(level, difficulty)
    potential = int(bet * mult)
    
    await message.answer(
        f"💎 **АЛМАЗЫ** — Уровень {level}/16\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_number(bet)} VC**\n"
        f"📊 Сложность: **{difficulty}** ({'3x3' if difficulty == 1 else '4x4'})\n\n"
        f"📈 Множитель: **x{mult:.2f}**\n"
        f"💵 Потенциал: **{format_number(potential)} VC**\n\n"
        f"🔍 Найди алмаз!",
        reply_markup=keyboard
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
            await callback.answer("❌ Сначала пройди хотя бы один уровень!", show_alert=True)
            return
        
        mult = DiamondsGame.get_multiplier(state['level'] - 1, state['difficulty'])
        winnings = int(state['bet'] * mult)
        
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        await db.close_game_session(session_id, "cashout", winnings)
        
        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ - ЗАБРАЛ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Пройдено уровней: **{state['level'] - 1}/16**\n"
            f"📈 Множитель: **x{mult:.2f}**\n\n"
            f"🏆 Выигрыш: **{format_number(winnings)} VC**"
        )
        await callback.answer(f"💰 +{format_number(winnings)} VC!", show_alert=True)
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
        await db.close_game_session(session_id, "loss", 0)
        
        keyboard_rows = DiamondsGame.create_keyboard(session_id, state['size'], state['diamond_pos'], True, cell)
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ - ПРОИГРЫШ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"❌ Не угадал!\n"
            f"🎯 Пройдено: **{state['level'] - 1}/16**\n\n"
            f"💔 Проигрыш: **{format_number(state['bet'])} VC**",
            reply_markup=keyboard
        )
        await callback.answer("❌ Не угадал!", show_alert=True)
        return
    
    state['level'] += 1
    
    if state['level'] > 16:
        mult = DiamondsGame.get_multiplier(16, state['difficulty'])
        winnings = int(state['bet'] * mult)
        
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        await db.close_game_session(session_id, "win", winnings)
        
        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ - ДЖЕКПОТ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎉 Прошёл все 16 уровней!\n"
            f"📈 Множитель: **x{mult:.2f}**\n\n"
            f"🏆 ДЖЕКПОТ: **{format_number(winnings)} VC**"
        )
        await callback.answer(f"🎉 ДЖЕКПОТ!", show_alert=True)
        return
    
    size = DiamondsGame.get_field_size(state['level'], state['difficulty'])
    state['size'] = size
    state['diamond_pos'] = random.randint(0, size * size - 1)
    
    await db.update_game_session(session_id, state, True)
    
    keyboard_rows = DiamondsGame.create_keyboard(session_id, size, state['diamond_pos'], False)
    prev_mult = DiamondsGame.get_multiplier(state['level'] - 1, state['difficulty'])
    prev_win = int(state['bet'] * prev_mult)
    keyboard_rows.append([
        InlineKeyboardButton(text=f"💰 Забрать {format_number(prev_win)} VC (x{prev_mult:.2f})", callback_data=f"diamond_cashout_{session_id}")
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    curr_mult = DiamondsGame.get_multiplier(state['level'], state['difficulty'])
    potential = int(state['bet'] * curr_mult)
    
    await callback.message.edit_text(
        f"💎 **АЛМАЗЫ** — Уровень {state['level']}/16\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Нашёл алмаз!\n"
        f"💰 Ставка: **{format_number(state['bet'])} VC**\n\n"
        f"📈 Множитель: **x{curr_mult:.2f}**\n"
        f"💵 Потенциал: **{format_number(potential)} VC**\n\n"
        f"🔍 Найди алмаз!",
        reply_markup=keyboard
    )
    await callback.answer("✅ Угадал!")


# ==================== РУЛЕТКА ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('рулетка'))
async def roulette_start(message: Message):
    text = message.text.lower().replace('рулетка', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        await message.answer(
            f"🎡 **РУЛЕТКА**\n\n"
            f"🎮 Использование: `рулетка [ставка]`\n\n"
            f"Пример: `рулетка 100`\n"
            f"Пример: `рулетка 100к`"
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала напиши /start")
        return
    
    bet = parse_amount(parts[0], user['coins'])
    
    if bet <= 0:
        await message.answer("❌ Укажи ставку!")
        return
    if bet > user['coins']:
        await message.answer(f"❌ Недостаточно монет!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Красное x2", callback_data=f"roulette_{bet}_red"),
            InlineKeyboardButton(text="⚫ Чёрное x2", callback_data=f"roulette_{bet}_black"),
        ],
        [
            InlineKeyboardButton(text="🟢 Зеро x36", callback_data=f"roulette_{bet}_zero"),
        ],
        [
            InlineKeyboardButton(text="1-12 x3", callback_data=f"roulette_{bet}_1-12"),
            InlineKeyboardButton(text="13-24 x3", callback_data=f"roulette_{bet}_13-24"),
            InlineKeyboardButton(text="25-36 x3", callback_data=f"roulette_{bet}_25-36"),
        ]
    ])
    
    await message.answer(
        f"🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_number(bet)} VC**\n\n"
        f"🎯 Выбери ставку:\n\n"
        f"🔴 **Красное** — x2\n"
        f"⚫ **Чёрное** — x2\n"
        f"🟢 **Зеро (0)** — x36\n"
        f"📊 **1-12 / 13-24 / 25-36** — x3",
        reply_markup=keyboard
    )


@games_router.callback_query(lambda c: c.data.startswith('roulette_'))
async def roulette_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet = int(parts[1])
    choice = parts[2]
    
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)
        return
    
    await db.update_coins(callback.from_user.id, -bet)
    
    await callback.message.edit_text(f"🎡 **РУЛЕТКА**\n\n🎰 Крутим колесо... 🌀")
    
    await asyncio.sleep(2)
    
    result = random.randint(0, 36)
    
    RED = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    BLACK = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]
    
    if result == 0:
        color_emoji = "🟢"
        color_name = "Зеро"
    elif result in RED:
        color_emoji = "🔴"
        color_name = "Красное"
    else:
        color_emoji = "⚫"
        color_name = "Чёрное"
    
    won = False
    mult = 0
    
    if choice == "red" and result in RED:
        won, mult = True, 2
    elif choice == "black" and result in BLACK:
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
        winnings = bet * mult
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        
        text = (
            f"🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎰 Выпало: {color_emoji} **{result}** ({color_name})\n\n"
            f"✅ **ПОБЕДА!**\n"
            f"📈 Множитель: **x{mult}**\n"
            f"💰 Выигрыш: **{format_number(winnings)} VC**"
        )
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        text = (
            f"🎡 **РУЛЕТКА**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎰 Выпало: {color_emoji} **{result}** ({color_name})\n\n"
            f"❌ **ПРОИГРЫШ**\n"
            f"💔 Потеряно: **{format_number(bet)} VC**"
        )
    
    await callback.message.edit_text(text)


# ==================== КРАШ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('краш'))
async def crash_start(message: Message):
    text = message.text.lower().replace('краш', '').strip()
    parts = text.split()
    
    if len(parts) < 2:
        await message.answer(
            f"📈 **КРАШ**\n\n"
            f"🎮 Использование: `краш [ставка] [вывод]`\n\n"
            f"Пример: `краш 100 2.5`\n"
            f"Пример: `краш 1к 10`\n\n"
            f"📊 Множитель вывода: от 1.01 до 505"
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала напиши /start")
        return
    
    bet = parse_amount(parts[0], user['coins'])
    
    try:
        cashout_at = float(parts[1].replace('x', '').replace(',', '.'))
    except:
        await message.answer("❌ Некорректный множитель!")
        return
    
    if bet <= 0:
        await message.answer("❌ Укажи ставку!")
        return
    if bet > user['coins']:
        await message.answer(f"❌ Недостаточно монет!")
        return
    if cashout_at < 1.01 or cashout_at > 505:
        await message.answer("❌ Множитель от 1.01 до 505!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    # Генерация точки краша
    rand = random.random()
    if rand < 0.33:
        crash_point = round(random.uniform(1.0, 1.5), 2)
    elif rand < 0.55:
        crash_point = round(random.uniform(1.5, 2.5), 2)
    elif rand < 0.75:
        crash_point = round(random.uniform(2.5, 5.0), 2)
    elif rand < 0.90:
        crash_point = round(random.uniform(5.0, 20.0), 2)
    elif rand < 0.98:
        crash_point = round(random.uniform(20.0, 100.0), 2)
    else:
        crash_point = round(random.uniform(100.0, 505.0), 2)
    
    msg = await message.answer(
        f"📈 **КРАШ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_number(bet)} VC**\n"
        f"🎯 Вывод на: **x{cashout_at}**\n\n"
        f"🚀 Запуск... **x1.00**"
    )
    
    current = 1.0
    step = 0.03
    
    while current < min(crash_point, cashout_at + 0.5):
        current = round(current + step, 2)
        step = round(step * 1.05, 3)
        
        if current >= crash_point:
            current = crash_point
            break
        
        if current >= cashout_at:
            break
        
        try:
            emoji = "🟢" if current < cashout_at * 0.7 else ("🟡" if current < cashout_at else "🔴")
            await msg.edit_text(
                f"📈 **КРАШ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 Ставка: **{format_number(bet)} VC**\n"
                f"🎯 Вывод на: **x{cashout_at}**\n\n"
                f"{emoji} Текущий: **x{current}**"
            )
        except:
            pass
        
        await asyncio.sleep(0.2)
    
    if cashout_at <= crash_point:
        winnings = int(bet * cashout_at)
        await db.update_coins(message.from_user.id, winnings)
        await db.update_stats(message.from_user.id, True, winnings)
        
        await msg.edit_text(
            f"📈 **КРАШ - УСПЕХ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Вывел на **x{cashout_at}**!\n"
            f"💥 Крашнуло на: **x{crash_point}**\n\n"
            f"🏆 Выигрыш: **{format_number(winnings)} VC**"
        )
    else:
        await db.update_stats(message.from_user.id, False, bet)
        
        await msg.edit_text(
            f"📈 **КРАШ - КРАХ!**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💥 Крашнуло на: **x{crash_point}**\n"
            f"🎯 Твой вывод: **x{cashout_at}**\n\n"
            f"💔 Проигрыш: **{format_number(bet)} VC**"
        )


# ==================== КОСТИ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('кости'))
async def dice_start(message: Message):
    text = message.text.lower().replace('кости', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        await message.answer(
            f"🎲 **КОСТИ**\n\n"
            f"🎮 Использование: `кости [ставка]`\n\n"
            f"Пример: `кости 100`"
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала напиши /start")
        return
    
    bet = parse_amount(parts[0], user['coins'])
    
    if bet <= 0:
        await message.answer("❌ Укажи ставку!")
        return
    if bet > user['coins']:
        await message.answer(f"❌ Недостаточно монет!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Больше 7 (x2.3)", callback_data=f"dice_{bet}_more"),
            InlineKeyboardButton(text="📉 Меньше 7 (x2.3)", callback_data=f"dice_{bet}_less"),
        ],
        [
            InlineKeyboardButton(text="🎯 Ровно 7 (x5.8)", callback_data=f"dice_{bet}_exact"),
        ]
    ])
    
    await message.answer(
        f"🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_number(bet)} VC**\n\n"
        f"🎯 Угадай сумму двух кубиков:\n\n"
        f"📈 **Больше 7** — x2.3\n"
        f"📉 **Меньше 7** — x2.3\n"
        f"🎯 **Ровно 7** — x5.8",
        reply_markup=keyboard
    )


@games_router.callback_query(lambda c: c.data.startswith('dice_'))
async def dice_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet = int(parts[1])
    choice = parts[2]
    
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)
        return
    
    await db.update_coins(callback.from_user.id, -bet)
    await callback.message.edit_text(f"🎲 **КОСТИ**\n\n🎰 Бросаем кубики...")
    
    dice1 = await callback.message.answer_dice(emoji="🎲")
    await asyncio.sleep(0.5)
    dice2 = await callback.message.answer_dice(emoji="🎲")
    
    await asyncio.sleep(4)
    
    total = dice1.dice.value + dice2.dice.value
    
    won = False
    mult = 0
    
    if choice == "more" and total > 7:
        won, mult = True, 2.3
    elif choice == "less" and total < 7:
        won, mult = True, 2.3
    elif choice == "exact" and total == 7:
        won, mult = True, 5.8
    
    choice_text = {"more": "Больше 7", "less": "Меньше 7", "exact": "Ровно 7"}.get(choice)
    
    if won:
        winnings = int(bet * mult)
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        
        text = (
            f"🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 Выпало: **{dice1.dice.value}** + **{dice2.dice.value}** = **{total}**\n"
            f"📝 Ставка: **{choice_text}**\n\n"
            f"✅ **ПОБЕДА!**\n"
            f"📈 Множитель: **x{mult}**\n"
            f"💰 Выигрыш: **{format_number(winnings)} VC**"
        )
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        text = (
            f"🎲 **КОСТИ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 Выпало: **{dice1.dice.value}** + **{dice2.dice.value}** = **{total}**\n"
            f"📝 Ставка: **{choice_text}**\n\n"
            f"❌ **ПРОИГРЫШ**\n"
            f"💔 Потеряно: **{format_number(bet)} VC**"
        )
    
    await callback.message.answer(text)


# ==================== ФУТБОЛ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('футбол'))
async def football_start(message: Message):
    text = message.text.lower().replace('футбол', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        await message.answer(f"⚽ **ФУТБОЛ**\n\n🎮 Использование: `футбол [ставка]`\n\nПример: `футбол 100`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала напиши /start")
        return
    
    bet = parse_amount(parts[0], user['coins'])
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚽ Гол (x1.8)", callback_data=f"football_{bet}_goal"),
            InlineKeyboardButton(text="❌ Мимо (x3.7)", callback_data=f"football_{bet}_miss"),
        ]
    ])
    
    await message.answer(
        f"⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_number(bet)} VC**\n\n"
        f"🎯 Угадай результат:\n\n"
        f"⚽ **Гол** — x1.8\n"
        f"❌ **Мимо** — x3.7",
        reply_markup=keyboard
    )


@games_router.callback_query(lambda c: c.data.startswith('football_'))
async def football_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet = int(parts[1])
    choice = parts[2]
    
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)
        return
    
    await db.update_coins(callback.from_user.id, -bet)
    await callback.message.edit_text(f"⚽ **ФУТБОЛ**\n\n🏃 Удар...")
    
    dice = await callback.message.answer_dice(emoji="⚽")
    await asyncio.sleep(4)
    
    is_goal = dice.dice.value >= 3  # 3,4,5 - гол
    won = (choice == "goal" and is_goal) or (choice == "miss" and not is_goal)
    mult = 1.8 if choice == "goal" else 3.7
    
    result_text = "⚽ ГОЛ!" if is_goal else "❌ Мимо!"
    
    if won:
        winnings = int(bet * mult)
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        
        text = f"⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Результат: **{result_text}**\n\n✅ **ПОБЕДА!**\n📈 x{mult}\n💰 +**{format_number(winnings)} VC**"
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        text = f"⚽ **ФУТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Результат: **{result_text}**\n\n❌ **ПРОИГРЫШ**\n💔 -{format_number(bet)} VC"
    
    await callback.message.answer(text)


# ==================== БАСКЕТБОЛ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('баскетбол'))
async def basketball_start(message: Message):
    text = message.text.lower().replace('баскетбол', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        await message.answer(f"🏀 **БАСКЕТБОЛ**\n\n🎮 Использование: `баскетбол [ставка]`\n\nПример: `баскетбол 100`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала напиши /start")
        return
    
    bet = parse_amount(parts[0], user['coins'])
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏀 Попал (x3.8)", callback_data=f"basketball_{bet}_goal"),
            InlineKeyboardButton(text="❌ Мимо (x1.9)", callback_data=f"basketball_{bet}_miss"),
        ]
    ])
    
    await message.answer(
        f"🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_number(bet)} VC**\n\n"
        f"🎯 Угадай результат:\n\n"
        f"🏀 **Попал** — x3.8\n"
        f"❌ **Мимо** — x1.9",
        reply_markup=keyboard
    )


@games_router.callback_query(lambda c: c.data.startswith('basketball_'))
async def basketball_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet = int(parts[1])
    choice = parts[2]
    
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)
        return
    
    await db.update_coins(callback.from_user.id, -bet)
    await callback.message.edit_text(f"🏀 **БАСКЕТБОЛ**\n\n🏃 Бросок...")
    
    dice = await callback.message.answer_dice(emoji="🏀")
    await asyncio.sleep(4)
    
    is_goal = dice.dice.value >= 4  # 4,5 - попал
    won = (choice == "goal" and is_goal) or (choice == "miss" and not is_goal)
    mult = 3.8 if choice == "goal" else 1.9
    
    result_text = "🏀 Попал!" if is_goal else "❌ Мимо!"
    
    if won:
        winnings = int(bet * mult)
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        
        text = f"🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Результат: **{result_text}**\n\n✅ **ПОБЕДА!**\n📈 x{mult}\n💰 +**{format_number(winnings)} VC**"
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        text = f"🏀 **БАСКЕТБОЛ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Результат: **{result_text}**\n\n❌ **ПРОИГРЫШ**\n💔 -{format_number(bet)} VC"
    
    await callback.message.answer(text)


# ==================== ДАРТС ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('дартс'))
async def darts_start(message: Message):
    text = message.text.lower().replace('дартс', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        await message.answer(f"🎯 **ДАРТС**\n\n🎮 Использование: `дартс [ставка]`\n\nПример: `дартс 100`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала напиши /start")
        return
    
    bet = parse_amount(parts[0], user['coins'])
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Центр (x5.8)", callback_data=f"darts_{bet}_center"),
            InlineKeyboardButton(text="❌ Мимо (x5.8)", callback_data=f"darts_{bet}_miss"),
        ],
        [
            InlineKeyboardButton(text="⚪ Белое (x1.9)", callback_data=f"darts_{bet}_white"),
            InlineKeyboardButton(text="🔴 Красное (x1.9)", callback_data=f"darts_{bet}_red"),
        ]
    ])
    
    await message.answer(
        f"🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_number(bet)} VC**\n\n"
        f"🎯 Угадай результат:\n\n"
        f"🎯 **Центр** — x5.8\n"
        f"❌ **Мимо** — x5.8\n"
        f"⚪ **Белое** — x1.9\n"
        f"🔴 **Красное** — x1.9",
        reply_markup=keyboard
    )


@games_router.callback_query(lambda c: c.data.startswith('darts_'))
async def darts_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet = int(parts[1])
    choice = parts[2]
    
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)
        return
    
    await db.update_coins(callback.from_user.id, -bet)
    await callback.message.edit_text(f"🎯 **ДАРТС**\n\n🏹 Бросок...")
    
    dice = await callback.message.answer_dice(emoji="🎯")
    await asyncio.sleep(4)
    
    value = dice.dice.value
    # 6 = центр, 1 = мимо, 2-3 = белое, 4-5 = красное
    result_map = {1: "miss", 2: "white", 3: "white", 4: "red", 5: "red", 6: "center"}
    result = result_map.get(value, "miss")
    
    result_text = {"center": "🎯 Центр!", "miss": "❌ Мимо!", "white": "⚪ Белое", "red": "🔴 Красное"}.get(result)
    mult = {"center": 5.8, "miss": 5.8, "white": 1.9, "red": 1.9}.get(choice, 1.9)
    
    won = (choice == result)
    
    if won:
        winnings = int(bet * mult)
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        
        text = f"🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Результат: **{result_text}**\n\n✅ **ПОБЕДА!**\n📈 x{mult}\n💰 +**{format_number(winnings)} VC**"
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        text = f"🎯 **ДАРТС**\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Результат: **{result_text}**\n\n❌ **ПРОИГРЫШ**\n💔 -{format_number(bet)} VC"
    
    await callback.message.answer(text)


# ==================== БОУЛИНГ ====================

@games_router.message(lambda m: m.text and m.text.lower().startswith('боулинг'))
async def bowling_start(message: Message):
    text = message.text.lower().replace('боулинг', '').strip()
    parts = text.split()
    
    if len(parts) < 1:
        await message.answer(f"🎳 **БОУЛИНГ**\n\n🎮 Использование: `боулинг [ставка]`\n\nПример: `боулинг 100`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала напиши /start")
        return
    
    bet = parse_amount(parts[0], user['coins'])
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎳 Страйк (x5.3)", callback_data=f"bowling_{bet}_strike"),
            InlineKeyboardButton(text="❌ Мимо (x5.3)", callback_data=f"bowling_{bet}_miss"),
        ],
        [
            InlineKeyboardButton(text="1️⃣-3️⃣ (x1.9)", callback_data=f"bowling_{bet}_1-3"),
            InlineKeyboardButton(text="4️⃣-5️⃣ (x1.9)", callback_data=f"bowling_{bet}_4-5"),
        ]
    ])
    
    await message.answer(
        f"🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Ставка: **{format_number(bet)} VC**\n\n"
        f"🎯 Угадай результат:\n\n"
        f"🎳 **Страйк** — x5.3\n"
        f"❌ **Мимо** — x5.3\n"
        f"1️⃣-3️⃣ **1-3 кегли** — x1.9\n"
        f"4️⃣-5️⃣ **4-5 кеглей** — x1.9",
        reply_markup=keyboard
    )


@games_router.callback_query(lambda c: c.data.startswith('bowling_'))
async def bowling_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet = int(parts[1])
    choice = parts[2]
    
    user = await db.get_user(callback.from_user.id)
    if user['coins'] < bet:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)
        return
    
    await db.update_coins(callback.from_user.id, -bet)
    await callback.message.edit_text(f"🎳 **БОУЛИНГ**\n\n🎳 Бросок...")
    
    dice = await callback.message.answer_dice(emoji="🎳")
    await asyncio.sleep(4)
    
    value = dice.dice.value
    # 6 = страйк, 1 = мимо, 2-3 = 1-3 кегли, 4-5 = 4-5 кеглей
    result_map = {1: "miss", 2: "1-3", 3: "1-3", 4: "4-5", 5: "4-5", 6: "strike"}
    result = result_map.get(value, "miss")
    
    result_text = {"strike": "🎳 СТРАЙК!", "miss": "❌ Мимо!", "1-3": f"🎳 {value} кегли", "4-5": f"🎳 {value} кеглей"}.get(result)
    mult = {"strike": 5.3, "miss": 5.3, "1-3": 1.9, "4-5": 1.9}.get(choice, 1.9)
    
    won = (choice == result)
    
    if won:
        winnings = int(bet * mult)
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        
        text = f"🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Результат: **{result_text}**\n\n✅ **ПОБЕДА!**\n📈 x{mult}\n💰 +**{format_number(winnings)} VC**"
    else:
        await db.update_stats(callback.from_user.id, False, bet)
        text = f"🎳 **БОУЛИНГ**\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Результат: **{result_text}**\n\n❌ **ПРОИГРЫШ**\n💔 -{format_number(bet)} VC"
    
    await callback.message.answer(text)


# ==================== DISABLED CALLBACK ====================

@games_router.callback_query(lambda c: c.data == 'game_disabled')
async def disabled_callback(callback: CallbackQuery):
    await callback.answer()
