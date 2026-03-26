import re
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import EMOJI, GPU_CONFIG, JOBS_CONFIG, ADMIN_IDS
from utils import format_coins, format_vibeton, parse_amount, format_number
from games import DiamondGame, MinesGame, RouletteGame, CrashGame, DiceGames
from farm import get_farm_info, get_farm_keyboard, collect_vibeton
from market import get_market_info, get_market_keyboard, get_current_price
from jobs import do_work

router = Router()

class GameStates(StatesGroup):
    waiting_mines_count = State()
    waiting_crash_cashout = State()
    waiting_dice_prediction = State()
    waiting_market_amount = State()
    waiting_market_price = State()
    waiting_transfer_user = State()
    waiting_transfer_amount = State()

# ==================== ПРОФИЛЬ ====================

@router.message(F.text.lower().in_(['я', 'б', 'проф', 'профиль', 'п', 'баланс']))
async def profile_handler(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )
        user = await db.get_user(message.from_user.id)
    
    winrate = (user['total_wins'] / user['total_games'] * 100) if user['total_games'] > 0 else 0
    
    text = (
        f"{EMOJI['user']} **ПРОФИЛЬ**\n"
        f"{'═' * 25}\n\n"
        f"👤 **{message.from_user.first_name}**\n"
        f"🆔 `{message.from_user.id}`\n\n"
        f"{'─' * 25}\n"
        f"{EMOJI['coin']} **Баланс:** {format_coins(user['coins'])}\n"
        f"{EMOJI['vibe']} **VibeTon:** {format_vibeton(user['vibeton'])}\n"
        f"{EMOJI['bank']} **В банке:** {format_coins(user['bank_balance'])}\n\n"
        f"{'─' * 25}\n"
        f"{EMOJI['game']} **Статистика игр:**\n"
        f"   📊 Всего игр: {user['total_games']}\n"
        f"   🏆 Побед: {user['total_wins']}\n"
        f"   📈 Винрейт: {winrate:.1f}%\n"
        f"   💰 Заработано: {format_coins(user['total_earned'])}\n"
        f"   💸 Проиграно: {format_coins(user['total_lost'])}"
    )
    
    await message.answer(text)

# ==================== ИГРЫ ====================

@router.message(F.text.lower().regexp(r'^алмазы?\s+(\S+)$'))
async def diamond_game(message: Message):
    match = re.match(r'^алмазы?\s+(\S+)$', message.text.lower())
    if not match:
        await message.answer(f"{EMOJI['info']} Использование: алмазы <ставка>")
        return
    
    user = await db.get_user(message.from_user.id)
    bet = parse_amount(match.group(1), user['coins'])
    
    if bet <= 0:
        await message.answer(f"{EMOJI['cross']} Некорректная ставка!")
        return
    
    if bet > user['coins']:
        await message.answer(f"{EMOJI['cross']} Недостаточно средств!")
        return
    
    # Создаем сессию игры
    state = DiamondGame.create_field(1)
    session_id = await db.create_game_session(
        message.from_user.id, 'diamond', bet, state
    )
    
    await db.update_coins(message.from_user.id, -bet)
    
    keyboard = DiamondGame.get_keyboard(state, session_id)
    
    await message.answer(
        f"💎 **АЛМАЗЫ** - Уровень 1/16\n\n"
        f"💰 Ставка: {format_coins(bet)}\n"
        f"🎯 Найди алмаз!\n\n"
        f"Выбери ячейку:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith('diamond_'))
async def diamond_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    session_id = int(parts[1])
    action = parts[2]
    
    session = await db.get_game_session(callback.from_user.id, 'diamond')
    if not session or session['id'] != session_id:
        await callback.answer("Игра не найдена!", show_alert=True)
        return
    
    import json
    state = json.loads(session['state'])
    bet = session['bet']
    
    if action == 'cashout':
        # Забрать выигрыш
        multiplier = state['level'] * 0.5
        winnings = int(bet * multiplier)
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        await db.close_game_session(session_id)
        
        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ** - Забрал!\n\n"
            f"✅ Прошел уровней: {state['level']}\n"
            f"🏆 Множитель: x{multiplier}\n"
            f"💰 Выигрыш: {format_coins(winnings)}"
        )
        return
    
    cell_id = int(action)
    
    if cell_id == state['diamond']:
        # Нашел алмаз!
        state['opened'].append(cell_id)
        state['level'] += 1
        
        if state['level'] > 16:
            # Прошел все уровни
            multiplier = 16 * 0.5
            winnings = int(bet * multiplier)
            await db.update_coins(callback.from_user.id, winnings)
            await db.update_stats(callback.from_user.id, True, winnings)
            await db.close_game_session(session_id)
            
            await callback.message.edit_text(
                f"💎 **АЛМАЗЫ** - ПОБЕДА!\n\n"
                f"🏆 Прошел все 16 уровней!\n"
                f"💰 Выигрыш: {format_coins(winnings)}"
            )
        else:
            # Переход на следующий уровень
            state = DiamondGame.create_field(state['level'])
            await db.update_game_session(session_id, state)
            
            keyboard = DiamondGame.get_keyboard(state, session_id)
            await callback.message.edit_text(
                f"💎 **АЛМАЗЫ** - Уровень {state['level']}/16\n\n"
                f"✅ Нашел алмаз!\n"
                f"💰 Ставка: {format_coins(bet)}\n"
                f"🎯 Найди следующий алмаз!",
                reply_markup=keyboard
            )
    else:
        # Проиграл
        state['opened'].append(cell_id)
        await db.update_stats(callback.from_user.id, False, bet)
        await db.close_game_session(session_id)
        
        await callback.message.edit_text(
            f"💎 **АЛМАЗЫ** - Проигрыш!\n\n"
            f"💔 Алмаз был в другой ячейке!\n"
            f"📊 Дошел до уровня: {state['level']}\n"
            f"💸 Проигрыш: {format_coins(bet)}"
        )
    
    await callback.answer()


@router.message(F.text.lower().regexp(r'^мины?\s+(\S+)(?:\s+(\d+))?$'))
async def mines_game(message: Message, state: FSMContext):
    match = re.match(r'^мины?\s+(\S+)(?:\s+(\d+))?$', message.text.lower())
    if not match:
        await message.answer(f"{EMOJI['info']} Использование: мины <ставка> [кол-во мин 1-24]")
        return
    
    user = await db.get_user(message.from_user.id)
    bet = parse_amount(match.group(1), user['coins'])
    mines_count = int(match.group(2)) if match.group(2) else 5
    
    if bet <= 0 or bet > user['coins']:
        await message.answer(f"{EMOJI['cross']} Некорректная ставка!")
        return
    
    if not 1 <= mines_count <= 24:
        await message.answer(f"{EMOJI['cross']} Количество мин: 1-24")
        return
    
    game_state = MinesGame.create_field(mines_count)
    session_id = await db.create_game_session(
        message.from_user.id, 'mines', bet, game_state
    )
    
    await db.update_coins(message.from_user.id, -bet)
    
    keyboard = MinesGame.get_keyboard(game_state, session_id)
    
    await message.answer(
        f"💣 **МИНЫ**\n\n"
        f"💰 Ставка: {format_coins(bet)}\n"
        f"💣 Мин на поле: {mines_count}\n"
        f"🎯 Открывай безопасные ячейки!",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith('mines_'))
async def mines_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    if parts[1] == 'disabled':
        await callback.answer()
        return
    
    session_id = int(parts[1])
    action = parts[2]
    
    session = await db.get_game_session(callback.from_user.id, 'mines')
    if not session or session['id'] != session_id:
        await callback.answer("Игра не найдена!", show_alert=True)
        return
    
    import json
    state = json.loads(session['state'])
    bet = session['bet']
    
    if action == 'cashout':
        multiplier = MinesGame.calculate_multiplier(len(state['opened']), state['mines_count'])
        winnings = int(bet * multiplier)
        await db.update_coins(callback.from_user.id, winnings)
        await db.update_stats(callback.from_user.id, True, winnings)
        await db.close_game_session(session_id)
        
        keyboard = MinesGame.get_keyboard(state, session_id, game_over=True)
        await callback.message.edit_text(
            f"💣 **МИНЫ** - Забрал!\n\n"
            f"✅ Открыто ячеек: {len(state['opened'])}\n"
            f"🏆 Множитель: x{multiplier}\n"
            f"💰 Выигрыш: {format_coins(winnings)}",
            reply_markup=keyboard
        )
        return
    
    cell_id = int(action)
    
    if cell_id in state['mines']:
        # Попал на мину
        state['opened'].append(cell_id)
        await db.update_stats(callback.from_user.id, False, bet)
        await db.close_game_session(session_id)
        
        keyboard = MinesGame.get_keyboard(state, session_id, game_over=True)
        await callback.message.edit_text(
            f"💣 **МИНЫ** - ВЗРЫВ!\n\n"
            f"💔 Попал на мину!\n"
            f"📊 Открыто ячеек: {len(state['opened']) - 1}\n"
            f"💸 Проигрыш: {format_coins(bet)}",
            reply_markup=keyboard
        )
    else:
        # Безопасная ячейка
        state['opened'].append(cell_id)
        await db.update_game_session(session_id, state)
        
        multiplier = MinesGame.calculate_multiplier(len(state['opened']), state['mines_count'])
        keyboard = MinesGame.get_keyboard(state, session_id)
        
        await callback.message.edit_text(
            f"💣 **МИНЫ**\n\n"
            f"💰 Ставка: {format_coins(bet)}\n"
            f"✅ Открыто: {len(state['opened'])}\n"
            f"🏆 Текущий множитель: x{multiplier}",
            reply_markup=keyboard
        )
    
    await callback.answer()


@router.message(F.text.lower().regexp(r'^рулетка\s+(\S+)\s+(.+)$'))
async def roulette_game(message: Message):
    match = re.match(r'^рулетка\s+(\S+)\s+(.+)$', message.text.lower())
    if not match:
        await message.answer(
            f"{EMOJI['info']} **Рулетка**\n\n"
            f"Использование: рулетка <ставка> <тип>\n\n"
            f"Типы ставок:\n"
            f"• 0-36 - конкретное число\n"
            f"• кра/красное - красные числа (x2)\n"
            f"• чер/черное - черные числа (x2)\n"
            f"• 1-12, 13-24, 25-36 - диапазоны (x3)"
        )
        return
    
    user = await db.get_user(message.from_user.id)
    bet = parse_amount(match.group(1), user['coins'])
    bet_type = match.group(2).strip()
    
    if bet <= 0 or bet > user['coins']:
        await message.answer(f"{EMOJI['cross']} Некорректная ставка!")
        return
    
    result, color, won, winnings, multiplier = await RouletteGame.play(
        message.from_user.id, bet, bet_type
    )
    
    color_emoji = "🟢" if color == "green" else ("🔴" if color == "red" else "⚫")
    
    if won:
        text = (
            f"🎡 **РУЛЕТКА**\n\n"
            f"🎯 Выпало: {color_emoji} **{result}**\n"
            f"✅ Ставка: {bet_type}\n\n"
            f"🏆 Множитель: x{multiplier}\n"
            f"💰 Выигрыш: {format_coins(winnings)}"
        )
    else:
        text = (
            f"🎡 **РУЛЕТКА**\n\n"
            f"🎯 Выпало: {color_emoji} **{result}**\n"
            f"❌ Ставка: {bet_type}\n\n"
            f"💔 Проигрыш: {format_coins(bet)}"
        )
    
    await message.answer(text)


@router.message(F.text.lower().regexp(r'^краш\s+(\S+)\s+(\S+)$'))
async def crash_game(message: Message):
    match = re.match(r'^краш\s+(\S+)\s+(\S+)$', message.text.lower())
    if not match:
        await message.answer(
            f"{EMOJI['info']} Использование: краш <ставка> <множитель вывода>\n"
            f"Пример: краш 1000 2.5"
        )
        return
    
    user = await db.get_user(message.from_user.id)
    bet = parse_amount(match.group(1), user['coins'])
    
    try:
        cashout = float(match.group(2).replace(',', '.').replace('x', ''))
    except:
        await message.answer(f"{EMOJI['cross']} Некорректный множитель!")
        return
    
    if bet <= 0 or bet > user['coins']:
        await message.answer(f"{EMOJI['cross']} Некорректная ставка!")
        return
    
    if cashout < 1.01 or cashout > 505:
        await message.answer(f"{EMOJI['cross']} Множитель должен быть от 1.01 до 505!")
        return
    
    await CrashGame.play(message.bot, message.chat.id, message.from_user.id, bet, cashout)


@router.message(F.text.lower().regexp(r'^футбол\s+(\S+)$'))
async def football_game(message: Message):
    match = re.match(r'^футбол\s+(\S+)$', message.text.lower())
    user = await db.get_user(message.from_user.id)
    bet = parse_amount(match.group(1), user['coins'])
    
    if bet <= 0 or bet > user['coins']:
        await message.answer(f"{EMOJI['cross']} Некорректная ставка!")
        return
    
    await DiceGames.play_football(message.bot, message.chat.id, message.from_user.id, bet)


@router.message(F.text.lower().regexp(r'^баскетбол\s+(\S+)$'))
async def basketball_game(message: Message):
    match = re.match(r'^баскетбол\s+(\S+)$', message.text.lower())
    user = await db.get_user(message.from_user.id)
    bet = parse_amount(match.group(1), user['coins'])
    
    if bet <= 0 or bet > user['coins']:
        await message.answer(f"{EMOJI['cross']} Некорректная ставка!")
        return
    
    await DiceGames.play_basketball(message.bot, message.chat.id, message.from_user.id, bet)


@router.message(F.text.lower().regexp(r'^боулинг\s+(\S+)$'))
async def bowling_game(message: Message):
    match = re.match(r'^боулинг\s+(\S+)$', message.text.lower())
    user = await db.get_user(message.from_user.id)
    bet = parse_amount(match.group(1), user['coins'])
    
    if bet <= 0 or bet > user['coins']:
        await message.answer(f"{EMOJI['cross']} Некорректная ставка!")
        return
    
    await DiceGames.play_bowling(message.bot, message.chat.id, message.from_user.id, bet)


@router.message(F.text.lower().regexp(r'^дартс\s+(\S+)$'))
async def darts_game(message: Message):
    match = re.match(r'^дартс\s+(\S+)$', message.text.lower())
    user = await db.get_user(message.from_user.id)
    bet = parse_amount(match.group(1), user['coins'])
    
    if bet <= 0 or bet > user['coins']:
        await message.answer(f"{EMOJI['cross']} Некорректная ставка!")
        return
    
    await DiceGames.play_darts(message.bot, message.chat.id, message.from_user.id, bet)


@router.message(F.text.lower().regexp(r'^кости\s+(\S+)\s+(больше|меньше|ровно)$'))
async def dice_game(message: Message):
    match = re.match(r'^кости\s+(\S+)\s+(больше|меньше|ровно)$', message.text.lower())
    if not match:
        await message.answer(
            f"{EMOJI['info']} Использование: кости <ставка> <больше/меньше/ровно>\n"
            f"Сумма двух кубиков сравнивается с 7"
        )
        return
    
    user = await db.get_user(message.from_user.id)
    bet = parse_amount(match.group(1), user['coins'])
    prediction = match.group(2)
    
    if bet <= 0 or bet > user['coins']:
        await message.answer(f"{EMOJI['cross']} Некорректная ставка!")
        return
    
    await DiceGames.play_dice(message.bot, message.chat.id, message.from_user.id, bet, prediction)


# ==================== РАБОТА ====================

@router.message(F.text.lower().in_(['работа', 'работы', 'раб']))
async def jobs_list(message: Message):
    text = f"{EMOJI['work']} **ДОСТУПНЫЕ РАБОТЫ**\n{'═' * 25}\n\n"
    
    for key, job in JOBS_CONFIG.items():
        text += (
            f"{job['emoji']} **{job['name']}**\n"
            f"   💰 {format_coins(job['min_salary'])} - {format_coins(job['max_salary'])}\n"
            f"   📋 {job['description']}\n"
            f"   ⏱ Команда: `работать {key}`\n\n"
        )
    
    await message.answer(text)


@router.message(F.text.lower().regexp(r'^работать\s+(\w+)$'))
async def work_handler(message: Message):
    match = re.match(r'^работать\s+(\w+)$', message.text.lower())
    job_key = match.group(1)
    
    if job_key not in JOBS_CONFIG:
        await message.answer(f"{EMOJI['cross']} Работа не найдена! Напиши `работа` для списка.")
        return
    
    await do_work(message.bot, message.chat.id, message.from_user.id, job_key)


# ==================== ФЕРМА ====================

@router.message(F.text.lower().in_(['ферма', 'майнинг', 'farm']))
async def farm_handler(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )
    
    text = await get_farm_info(message.from_user.id)
    keyboard = get_farm_keyboard(message.from_user.id)
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith('buy_gpu_'))
async def buy_gpu_callback(callback: CallbackQuery):
    gpu_type = callback.data.replace('buy_gpu_', '')
    
    if gpu_type not in GPU_CONFIG:
        await callback.answer("Ошибка!", show_alert=True)
        return
    
    gpu = GPU_CONFIG[gpu_type]
    current_price = await db.get_gpu_price(callback.from_user.id, gpu_type, gpu['base_price'])
    
    success, result = await db.buy_gpu(callback.from_user.id, gpu_type, current_price)
    
    if success:
        await callback.answer(f"✅ Куплена {gpu['name']}!", show_alert=True)
        text = await get_farm_info(callback.from_user.id)
        keyboard = get_farm_keyboard(callback.from_user.id)
        await callback.message.edit_text(text, reply_markup=keyboard)
    elif result == "max":
        await callback.answer("❌ Максимум 10 таких видеокарт!", show_alert=True)
    else:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)


@router.callback_query(F.data == 'collect_farm')
async def collect_farm_callback(callback: CallbackQuery):
    amount, status = await collect_vibeton(callback.from_user.id)
    
    if status == "success":
        await callback.answer(f"✅ Собрано {amount:.2f} VibeTon!", show_alert=True)
        text = await get_farm_info(callback.from_user.id)
        keyboard = get_farm_keyboard(callback.from_user.id)
        await callback.message.edit_text(text, reply_markup=keyboard)
    elif status == "too_early":
        await callback.answer("⏰ Пока нечего собирать!", show_alert=True)
    else:
        await callback.answer("❌ Сначала купи видеокарту!", show_alert=True)


@router.callback_query(F.data == 'refresh_farm')
async def refresh_farm_callback(callback: CallbackQuery):
    text = await get_farm_info(callback.from_user.id)
    keyboard = get_farm_keyboard(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ==================== РЫНОК ====================

@router.message(F.text.lower().in_(['рынок', 'маркет', 'market']))
async def market_handler(message: Message):
    text = await get_market_info()
    keyboard = get_market_keyboard()
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == 'market_refresh')
async def market_refresh_callback(callback: CallbackQuery):
    text = await get_market_info()
    keyboard = get_market_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ==================== ТОПЫ ====================

@router.message(F.text.lower().in_(['топ', 'top', 'рейтинг']))
async def top_handler(message: Message):
    top_coins = await db.get_top_coins(10)
    top_vibeton = await db.get_top_vibeton(10)
    
    text = f"{EMOJI['top']} **ТОП-10 ИГРОКОВ**\n{'═' * 25}\n\n"
    
    text += f"💎 **По VineCoin:**\n"
    for i, user in enumerate(top_coins, 1):
        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"{i}."))
        name = user['first_name'] or user['username'] or 'Аноним'
        text += f"{medal} {name}: {format_coins(user['coins'])}\n"
    
    text += f"\n🔮 **По VibeTon:**\n"
    for i, user in enumerate(top_vibeton, 1):
        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"{i}."))
        name = user['first_name'] or user['username'] or 'Аноним'
        text += f"{medal} {name}: {format_vibeton(user['vibeton'])}\n"
    
    await message.answer(text)


# ==================== БАНК ====================

@router.message(F.text.lower().in_(['банк', 'bank']))
async def bank_handler(message: Message):
    user = await db.get_user(message.from_user.id)
    
    text = (
        f"{EMOJI['bank']} **БАНК**\n"
        f"{'═' * 25}\n\n"
        f"💰 На руках: {format_coins(user['coins'])}\n"
        f"🏦 В банке: {format_coins(user['bank_balance'])}\n\n"
        f"{'─' * 25}\n"
        f"📥 `депозит <сумма>` - положить\n"
        f"📤 `снять <сумма>` - снять\n"
        f"💸 `перевод @user <сумма>` - перевести"
    )
    
    await message.answer(text)


@router.message(F.text.lower().regexp(r'^депозит\s+(\S+)$'))
async def deposit_handler(message: Message):
    match = re.match(r'^депозит\s+(\S+)$', message.text.lower())
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(match.group(1), user['coins'])
    
    if amount <= 0:
        await message.answer(f"{EMOJI['cross']} Некорректная сумма!")
        return
    
    success = await db.deposit_to_bank(message.from_user.id, amount)
    
    if success:
        await message.answer(
            f"{EMOJI['check']} Успешно положено {format_coins(amount)} в банк!"
        )
    else:
        await message.answer(f"{EMOJI['cross']} Недостаточно средств!")


@router.message(F.text.lower().regexp(r'^снять\s+(\S+)$'))
async def withdraw_handler(message: Message):
    match = re.match(r'^снять\s+(\S+)$', message.text.lower())
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(match.group(1), user['bank_balance'])
    
    if amount <= 0:
        await message.answer(f"{EMOJI['cross']} Некорректная сумма!")
        return
    
    success = await db.withdraw_from_bank(message.from_user.id, amount)
    
    if success:
        await message.answer(
            f"{EMOJI['check']} Успешно снято {format_coins(amount)} из банка!"
        )
    else:
        await message.answer(f"{EMOJI['cross']} Недостаточно средств в банке!")


@router.message(F.text.lower().regexp(r'^перевод\s+@?(\w+)\s+(\S+)$'))
async def transfer_handler(message: Message):
    match = re.match(r'^перевод\s+@?(\w+)\s+(\S+)$', message.text.lower())
    username = match.group(1)
    
    user = await db.get_user(message.from_user.id)
    target = await db.get_user_by_username(username)
    
    if not target:
        await message.answer(f"{EMOJI['cross']} Пользователь не найден!")
        return
    
    if target['user_id'] == message.from_user.id:
        await message.answer(f"{EMOJI['cross']} Нельзя перевести себе!")
        return
    
    amount = parse_amount(match.group(2), user['coins'])
    
    if amount <= 0:
        await message.answer(f"{EMOJI['cross']} Некорректная сумма!")
        return
    
    success = await db.transfer_coins(message.from_user.id, target['user_id'], amount)
    
    if success:
        await message.answer(
            f"{EMOJI['check']} Успешно переведено {format_coins(amount)} пользователю @{username}!"
        )
    else:
        await message.answer(f"{EMOJI['cross']} Недостаточно средств!")


# ==================== ПРОМОКОДЫ ====================

@router.message(F.text.lower().regexp(r'^промо(?:код)?\s+(\S+)$'))
async def promo_handler(message: Message):
    match = re.match(r'^промо(?:код)?\s+(\S+)$', message.text.lower())
    code = match.group(1).upper()
    
    success, result = await db.use_promo(message.from_user.id, code)
    
    if success:
        rewards = []
        if result['coins_reward'] > 0:
            rewards.append(f"💎 {format_coins(result['coins_reward'])}")
        if result['vibeton_reward'] > 0:
            rewards.append(f"🔮 {format_vibeton(result['vibeton_reward'])}")
        
        await message.answer(
            f"{EMOJI['promo']} **ПРОМОКОД АКТИВИРОВАН!**\n\n"
            f"🎁 Получено:\n" + "\n".join(rewards)
        )
    elif result == "not_found":
        await message.answer(f"{EMOJI['cross']} Промокод не найден!")
    elif result == "expired":
        await message.answer(f"{EMOJI['cross']} Промокод больше недействителен!")
    else:
        await message.answer(f"{EMOJI['cross']} Ты уже использовал этот промокод!")


# ==================== ПОМОЩЬ ====================

@router.message(F.text.lower().in_(['помощь', 'help', 'команды', 'хелп']))
async def help_handler(message: Message):
    text = (
        f"{EMOJI['help']} **ЦЕНТР ПОМОЩИ**\n"
        f"{'═' * 25}\n\n"
        
        f"👤 **Профиль:**\n"
        f"• `я` / `профиль` / `б` - профиль\n\n"
        
        f"🎮 **Игры:**\n"
        f"• `алмазы <ставка>` - найди алмаз\n"
        f"• `мины <ставка> [мин]` - открой ячейки\n"
        f"• `рулетка <ставка> <тип>` - рулетка\n"
        f"• `краш <ставка> <x>` - краш\n"
        f"• `футбол <ставка>` - ⚽\n"
        f"• `баскетбол <ставка>` - 🏀\n"
        f"• `боулинг <ставка>` - 🎳\n"
        f"• `дартс <ставка>` - 🎯\n"
        f"• `кости <ставка> <>/</=> ` - 🎲\n\n"
        
        f"💼 **Работа:**\n"
        f"• `работа` - список работ\n"
        f"• `работать <тип>` - работать\n\n"
        
        f"⛏️ **Ферма:**\n"
        f"• `ферма` - управление фермой\n\n"
        
        f"🛒 **Рынок:**\n"
        f"• `рынок` - торговля VibeTon\n\n"
        
        f"🏦 **Банк:**\n"
        f"• `банк` - меню банка\n"
        f"• `депозит <сумма>` - положить\n"
        f"• `снять <сумма>` - снять\n"
        f"• `перевод @user <сумма>` - перевод\n\n"
        
        f"📊 **Другое:**\n"
        f"• `топ` - рейтинг игроков\n"
        f"• `промо <код>` - промокод\n"
    )
    
    await message.answer(text)


# ==================== АДМИН ====================

@router.message(F.text.lower().regexp(r'^абан\s+(\d+)$'))
async def admin_ban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    match = re.match(r'^абан\s+(\d+)$', message.text.lower())
    target_id = int(match.group(1))
    
    await db.ban_user(target_id, True)
    await message.answer(f"✅ Пользователь {target_id} заблокирован!")


@router.message(F.text.lower().regexp(r'^аразбан\s+(\d+)$'))
async def admin_unban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    match = re.match(r'^аразбан\s+(\d+)$', message.text.lower())
    target_id = int(match.group(1))
    
    await db.ban_user(target_id, False)
    await message.answer(f"✅ Пользователь {target_id} разблокирован!")


@router.message(F.text.lower().regexp(r'^авыдать\s+(\d+)\s+(\d+)(?:\s+(вт))?$'))
async def admin_give(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    match = re.match(r'^авыдать\s+(\d+)\s+(\d+)(?:\s+(вт))?$', message.text.lower())
    target_id = int(match.group(1))
    amount = int(match.group(2))
    is_vt = match.group(3) == 'вт'
    
    if is_vt:
        await db.update_vibeton(target_id, amount)
        await message.answer(f"✅ Выдано {amount} VT пользователю {target_id}!")
    else:
        await db.update_coins(target_id, amount)
        await message.answer(f"✅ Выдано {format_coins(amount)} пользователю {target_id}!")


@router.message(F.text.lower().regexp(r'^астат\s+(\d+)$'))
async def admin_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    match = re.match(r'^астат\s+(\d+)$', message.text.lower())
    target_id = int(match.group(1))
    
    user = await db.get_user(target_id)
    if not user:
        await message.answer("❌ Пользователь не найден!")
        return
    
    text = (
        f"📊 **Статистика игрока**\n"
        f"{'═' * 25}\n\n"
        f"🆔 ID: `{user['user_id']}`\n"
        f"👤 Username: @{user['username']}\n"
        f"📛 Имя: {user['first_name']}\n\n"
        f"💎 VC: {format_coins(user['coins'])}\n"
        f"🔮 VT: {format_vibeton(user['vibeton'])}\n"
        f"🏦 Банк: {format_coins(user['bank_balance'])}\n\n"
        f"🎮 Игр: {user['total_games']}\n"
        f"🏆 Побед: {user['total_wins']}\n"
        f"💰 Заработано: {format_coins(user['total_earned'])}\n"
        f"💸 Проиграно: {format_coins(user['total_lost'])}\n\n"
        f"🚫 Бан: {'Да' if user['is_banned'] else 'Нет'}"
    )
    
    await message.answer(text)


@router.message(F.text.lower().regexp(r'^асоздатьпромо\s+(\S+)\s+(\d+)(?:\s+(\d+))?(?:\s+(\d+))?$'))
async def admin_create_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    match = re.match(r'^асоздатьпромо\s+(\S+)\s+(\d+)(?:\s+(\d+))?(?:\s+(\d+))?$', message.text.lower())
    code = match.group(1).upper()
    coins = int(match.group(2))
    vibeton = float(match.group(3)) if match.group(3) else 0
    max_uses = int(match.group(4)) if match.group(4) else 100
    
    await db.create_promo(code, coins, vibeton, max_uses)
    await message.answer(
        f"✅ Промокод создан!\n\n"
        f"📝 Код: `{code}`\n"
        f"💎 VC: {format_coins(coins)}\n"
        f"🔮 VT: {format_vibeton(vibeton)}\n"
        f"👥 Макс. использований: {max_uses}"
    )


@router.message(F.text.lower() == 'астатистика')
async def admin_global_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    total_users = await db.get_all_users_count()
    
    await message.answer(
        f"📊 **Глобальная статистика**\n"
        f"{'═' * 25}\n\n"
        f"👥 Всего пользователей: {total_users}"
    )


# ==================== СТАРТ ====================

@router.message(CommandStart())
async def start_handler(message: Message):
    await db.create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    text = (
        f"🎮 **Добро пожаловать в VibeTon Bot!**\n"
        f"{'═' * 25}\n\n"
        f"Это казино-бот с множеством игр,\n"
        f"фермой майнинга и торговлей!\n\n"
        f"💎 Тебе начислено **10,000 VC**\n\n"
        f"📝 Напиши `помощь` для списка команд!"
    )
    
    await message.answer(text)
