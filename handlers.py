import re
import random
import asyncio
import json
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import EMOJI, GPU_CONFIG, JOBS_CONFIG, ADMIN_IDS
from utils import format_coins, format_vibeton, parse_amount, format_number

router = Router()


# ==================== FSM STATES ====================

class GameStates(StatesGroup):
    waiting_bet = State()
    waiting_choice = State()


# ==================== ПРОФИЛЬ (компактный) ====================

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
        f"👤 **{message.from_user.first_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 Баланс: **{format_number(user['coins'])} VC**\n"
        f"🔮 VibeTon: **{user['vibeton']:.2f} VT**\n"
        f"🏦 Банк: **{format_number(user['bank_balance'])} VC**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 Игр: {user['total_games']} | 🏆 Побед: {user['total_wins']}\n"
        f"📈 Винрейт: {winrate:.1f}%"
    )
    
    await message.answer(text)


# ==================== ИГРА: АЛМАЗЫ ====================

@router.message(F.text.lower().startswith('алмаз'))
async def diamond_start(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 2:
        await message.answer("💎 **Алмазы**\n\nИспользование: `алмазы 1000`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала напиши /start")
        return
    
    bet = parse_amount(parts[1], user['coins'])
    
    if bet <= 0:
        await message.answer("❌ Укажи ставку!")
        return
    if bet > user['coins']:
        await message.answer("❌ Недостаточно монет!")
        return
    
    # Создаем игру
    diamond_pos = random.randint(0, 3)
    state = {'diamond': diamond_pos, 'level': 1, 'bet': bet}
    
    await db.update_coins(message.from_user.id, -bet)
    
    # Сохраняем состояние в callback_data
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❓", callback_data=f"gem_{bet}_{diamond_pos}_0"),
            InlineKeyboardButton(text="❓", callback_data=f"gem_{bet}_{diamond_pos}_1"),
        ],
        [
            InlineKeyboardButton(text="❓", callback_data=f"gem_{bet}_{diamond_pos}_2"),
            InlineKeyboardButton(text="❓", callback_data=f"gem_{bet}_{diamond_pos}_3"),
        ]
    ])
    
    await message.answer(
        f"💎 **АЛМАЗЫ**\n\n"
        f"💰 Ставка: {format_number(bet)} VC\n"
        f"🎯 Найди алмаз!",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith('gem_'))
async def diamond_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet = int(parts[1])
    diamond_pos = int(parts[2])
    chosen = int(parts[3])
    
    if chosen == diamond_pos:
        # Выиграл
        win = int(bet * 1.8)
        await db.update_coins(callback.from_user.id, win)
        await db.update_stats(callback.from_user.id, True, win)
        
        await callback.message.edit_text(
            f"💎 **ПОБЕДА!**\n\n"
            f"✅ Ты нашел алмаз!\n"
            f"💰 Выигрыш: **{format_number(win)} VC**"
        )
    else:
        # Проиграл
        await db.update_stats(callback.from_user.id, False, bet)
        
        await callback.message.edit_text(
            f"💎 **ПРОИГРЫШ**\n\n"
            f"❌ Алмаз был в другой ячейке\n"
            f"💔 -{format_number(bet)} VC"
        )
    
    await callback.answer()


# ==================== ИГРА: МИНЫ ====================

@router.message(F.text.lower().startswith('мин'))
async def mines_start(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 2:
        await message.answer("💣 **Мины**\n\nИспользование: `мины 1000`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[1], user['coins'])
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    # Создаем поле 3x3 с 3 минами
    cells = list(range(9))
    mines = random.sample(cells, 3)
    
    await db.update_coins(message.from_user.id, -bet)
    
    # Кодируем мины в строку
    mines_str = ','.join(map(str, mines))
    
    keyboard = []
    for row in range(3):
        row_btns = []
        for col in range(3):
            cell = row * 3 + col
            row_btns.append(
                InlineKeyboardButton(
                    text="🟦",
                    callback_data=f"mine_{bet}_{mines_str}_0_{cell}"
                )
            )
        keyboard.append(row_btns)
    
    await message.answer(
        f"💣 **МИНЫ**\n\n"
        f"💰 Ставка: {format_number(bet)} VC\n"
        f"💣 Мин: 3 | 🎯 Открывай ячейки!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


@router.callback_query(F.data.startswith('mine_'))
async def mines_callback(callback: CallbackQuery):
    parts = callback.data.split('_')
    bet = int(parts[1])
    mines = list(map(int, parts[2].split(',')))
    opened_count = int(parts[3])
    chosen = int(parts[4])
    
    if chosen in mines:
        # Попал на мину
        await db.update_stats(callback.from_user.id, False, bet)
        
        # Показываем все мины
        keyboard = []
        for row in range(3):
            row_btns = []
            for col in range(3):
                cell = row * 3 + col
                if cell in mines:
                    text = "💣"
                elif cell == chosen:
                    text = "💥"
                else:
                    text = "🟦"
                row_btns.append(InlineKeyboardButton(text=text, callback_data="none"))
            keyboard.append(row_btns)
        
        await callback.message.edit_text(
            f"💣 **ВЗРЫВ!**\n\n"
            f"💔 Проигрыш: {format_number(bet)} VC",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    else:
        # Безопасная ячейка
        opened_count += 1
        mult = 1 + (opened_count * 0.5)
        
        if opened_count >= 6:
            # Макс выигрыш
            win = int(bet * mult)
            await db.update_coins(callback.from_user.id, win)
            await db.update_stats(callback.from_user.id, True, win)
            
            await callback.message.edit_text(
                f"💣 **ПОБЕДА!**\n\n"
                f"✅ Открыто: {opened_count}/6\n"
                f"💰 Выигрыш: **{format_number(win)} VC**"
            )
        else:
            # Продолжаем
            mines_str = ','.join(map(str, mines))
            
            keyboard = []
            for row in range(3):
                row_btns = []
                for col in range(3):
                    cell = row * 3 + col
                    if cell == chosen:
                        text = "💎"
                        cb = "none"
                    else:
                        text = "🟦"
                        cb = f"mine_{bet}_{mines_str}_{opened_count}_{cell}"
                    row_btns.append(InlineKeyboardButton(text=text, callback_data=cb))
                keyboard.append(row_btns)
            
            # Кнопка забрать
            win = int(bet * mult)
            keyboard.append([
                InlineKeyboardButton(
                    text=f"💰 Забрать {format_number(win)} VC (x{mult:.1f})",
                    callback_data=f"mine_take_{win}"
                )
            ])
            
            await callback.message.edit_text(
                f"💣 **МИНЫ**\n\n"
                f"✅ Открыто: {opened_count}/6\n"
                f"📈 Множитель: x{mult:.1f}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
    
    await callback.answer()


@router.callback_query(F.data.startswith('mine_take_'))
async def mines_take(callback: CallbackQuery):
    win = int(callback.data.split('_')[2])
    
    await db.update_coins(callback.from_user.id, win)
    await db.update_stats(callback.from_user.id, True, win)
    
    await callback.message.edit_text(
        f"💣 **ЗАБРАЛ!**\n\n"
        f"💰 Выигрыш: **{format_number(win)} VC**"
    )
    await callback.answer()


@router.callback_query(F.data == "none")
async def none_callback(callback: CallbackQuery):
    await callback.answer()


# ==================== ИГРА: РУЛЕТКА ====================

@router.message(F.text.lower().startswith('рулетка'))
async def roulette_game(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 3:
        await message.answer(
            "🎡 **Рулетка**\n\n"
            "Использование: `рулетка 1000 красное`\n\n"
            "Ставки: красное, черное, зеро, 1-12, 13-24, 25-36"
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[1], user['coins'])
    bet_type = parts[2]
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    # Крутим рулетку
    result = random.randint(0, 36)
    
    red_numbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    color = "🟢" if result == 0 else ("🔴" if result in red_numbers else "⚫")
    
    won = False
    mult = 0
    
    if bet_type in ['красное', 'красный', 'кра', 'red']:
        if result in red_numbers:
            won = True
            mult = 2
    elif bet_type in ['черное', 'черный', 'чер', 'black']:
        if result != 0 and result not in red_numbers:
            won = True
            mult = 2
    elif bet_type in ['зеро', 'zero', '0']:
        if result == 0:
            won = True
            mult = 36
    elif bet_type == '1-12':
        if 1 <= result <= 12:
            won = True
            mult = 3
    elif bet_type == '13-24':
        if 13 <= result <= 24:
            won = True
            mult = 3
    elif bet_type == '25-36':
        if 25 <= result <= 36:
            won = True
            mult = 3
    
    if won:
        win = bet * mult
        await db.update_coins(message.from_user.id, win - bet)
        await db.update_stats(message.from_user.id, True, win)
        text = f"🎡 Выпало: {color} **{result}**\n\n✅ Выигрыш: **{format_number(win)} VC**"
    else:
        await db.update_coins(message.from_user.id, -bet)
        await db.update_stats(message.from_user.id, False, bet)
        text = f"🎡 Выпало: {color} **{result}**\n\n❌ Проигрыш: {format_number(bet)} VC"
    
    await message.answer(text)


# ==================== ИГРА: КРАШ ====================

@router.message(F.text.lower().startswith('краш'))
async def crash_game(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 3:
        await message.answer("📈 **Краш**\n\nИспользование: `краш 1000 2.5`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[1], user['coins'])
    
    try:
        cashout = float(parts[2].replace('x', '').replace(',', '.'))
    except:
        await message.answer("❌ Укажи множитель! Пример: `краш 1000 2.0`")
        return
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    if cashout < 1.1 or cashout > 100:
        await message.answer("❌ Множитель от 1.1 до 100!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    # Генерируем точку краша
    crash_point = round(random.uniform(1.0, 10.0), 2)
    if random.random() < 0.1:  # 10% шанс на большой множитель
        crash_point = round(random.uniform(5.0, 50.0), 2)
    
    msg = await message.answer(f"📈 **КРАШ**\n\n🚀 Запуск...")
    
    # Анимация
    current = 1.0
    while current < min(crash_point, cashout):
        current = round(current + random.uniform(0.1, 0.3), 2)
        await asyncio.sleep(0.4)
        try:
            await msg.edit_text(f"📈 **КРАШ**\n\n🚀 Множитель: **x{current}**")
        except:
            pass
    
    if cashout <= crash_point:
        # Успел вывести
        win = int(bet * cashout)
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await msg.edit_text(
            f"📈 **КРАШ**\n\n"
            f"✅ Вывел на **x{cashout}**!\n"
            f"💰 Выигрыш: **{format_number(win)} VC**"
        )
    else:
        # Крашнуло
        await db.update_stats(message.from_user.id, False, bet)
        await msg.edit_text(
            f"📈 **КРАШ**\n\n"
            f"💥 Крашнуло на **x{crash_point}**\n"
            f"❌ Проигрыш: {format_number(bet)} VC"
        )


# ==================== ИГРЫ С АНИМАЦИЕЙ TELEGRAM ====================

@router.message(F.text.lower().startswith('футбол'))
async def football_game(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 2:
        await message.answer("⚽ **Футбол**\n\nИспользование: `футбол 1000`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[1], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    dice = await message.answer_dice(emoji="⚽")
    value = dice.dice.value  # 1-5
    
    await asyncio.sleep(4)
    
    if value >= 3:  # Гол
        win = int(bet * 1.8)
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await message.answer(f"⚽ **ГОЛ!**\n\n💰 +{format_number(win)} VC")
    else:
        win = int(bet * 0.5)  # Утешительный приз
        await db.update_coins(message.from_user.id, win)
        await message.answer(f"⚽ **Мимо!**\n\n💰 +{format_number(win)} VC")


@router.message(F.text.lower().startswith('баскетбол'))
async def basketball_game(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 2:
        await message.answer("🏀 **Баскетбол**\n\nИспользование: `баскетбол 1000`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[1], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    dice = await message.answer_dice(emoji="🏀")
    value = dice.dice.value
    
    await asyncio.sleep(4)
    
    if value >= 4:  # Попал
        win = int(bet * 2.5)
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await message.answer(f"🏀 **ПОПАЛ!**\n\n💰 +{format_number(win)} VC")
    else:
        await db.update_stats(message.from_user.id, False, bet)
        await message.answer(f"🏀 **Мимо!**\n\n❌ -{format_number(bet)} VC")


@router.message(F.text.lower().startswith('боулинг'))
async def bowling_game(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 2:
        await message.answer("🎳 **Боулинг**\n\nИспользование: `боулинг 1000`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[1], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    dice = await message.answer_dice(emoji="🎳")
    value = dice.dice.value
    
    await asyncio.sleep(4)
    
    if value == 6:  # Страйк
        win = int(bet * 5)
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await message.answer(f"🎳 **СТРАЙК!**\n\n💰 +{format_number(win)} VC")
    elif value >= 3:
        win = int(bet * 1.5)
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await message.answer(f"🎳 Сбито: {value}\n\n💰 +{format_number(win)} VC")
    else:
        await db.update_stats(message.from_user.id, False, bet)
        await message.answer(f"🎳 Сбито: {value}\n\n❌ -{format_number(bet)} VC")


@router.message(F.text.lower().startswith('дартс'))
async def darts_game(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 2:
        await message.answer("🎯 **Дартс**\n\nИспользование: `дартс 1000`")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[1], user['coins'])
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    dice = await message.answer_dice(emoji="🎯")
    value = dice.dice.value
    
    await asyncio.sleep(4)
    
    if value == 6:  # Центр
        win = int(bet * 5)
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await message.answer(f"🎯 **ЦЕНТР!**\n\n💰 +{format_number(win)} VC")
    elif value >= 3:
        win = int(bet * 1.8)
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await message.answer(f"🎯 Очки: {value}\n\n💰 +{format_number(win)} VC")
    else:
        await db.update_stats(message.from_user.id, False, bet)
        await message.answer(f"🎯 Мимо!\n\n❌ -{format_number(bet)} VC")


@router.message(F.text.lower().startswith('кости'))
async def dice_game(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 3:
        await message.answer(
            "🎲 **Кости**\n\n"
            "Использование: `кости 1000 больше`\n"
            "Варианты: больше, меньше, ровно (7)"
        )
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    bet = parse_amount(parts[1], user['coins'])
    choice = parts[2]
    
    if bet <= 0 or bet > user['coins']:
        await message.answer("❌ Некорректная ставка!")
        return
    
    if choice not in ['больше', 'меньше', 'ровно']:
        await message.answer("❌ Выбери: больше, меньше или ровно")
        return
    
    await db.update_coins(message.from_user.id, -bet)
    
    dice1 = await message.answer_dice(emoji="🎲")
    await asyncio.sleep(0.5)
    dice2 = await message.answer_dice(emoji="🎲")
    
    await asyncio.sleep(3)
    
    total = dice1.dice.value + dice2.dice.value
    
    won = False
    mult = 2
    
    if choice == 'больше' and total > 7:
        won = True
    elif choice == 'меньше' and total < 7:
        won = True
    elif choice == 'ровно' and total == 7:
        won = True
        mult = 5
    
    if won:
        win = int(bet * mult)
        await db.update_coins(message.from_user.id, win)
        await db.update_stats(message.from_user.id, True, win)
        await message.answer(f"🎲 Сумма: **{total}**\n\n✅ +{format_number(win)} VC")
    else:
        await db.update_stats(message.from_user.id, False, bet)
        await message.answer(f"🎲 Сумма: **{total}**\n\n❌ -{format_number(bet)} VC")


# ==================== РАБОТА ====================

@router.message(F.text.lower().in_(['работа', 'работы', 'раб']))
async def jobs_list(message: Message):
    text = "💼 **РАБОТЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for key, job in JOBS_CONFIG.items():
        text += f"{job['emoji']} **{job['name']}**\n"
        text += f"└ {format_number(job['min_salary'])}-{format_number(job['max_salary'])} VC\n"
        text += f"└ Команда: `работать {key}`\n\n"
    
    await message.answer(text)


@router.message(F.text.lower().startswith('работать'))
async def work_handler(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 2:
        await message.answer("💼 Укажи работу! Напиши `работа` для списка")
        return
    
    job_key = parts[1]
    if job_key not in JOBS_CONFIG:
        await message.answer("❌ Работа не найдена!")
        return
    
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    
    # Проверка кулдауна
    can_work = await db.can_work(message.from_user.id)
    if not can_work:
        cooldown = await db.get_work_cooldown(message.from_user.id)
        mins = cooldown // 60
        secs = cooldown % 60
        await message.answer(f"⏰ Отдохни ещё **{mins}м {secs}с**")
        return
    
    job = JOBS_CONFIG[job_key]
    salary = random.randint(job['min_salary'], job['max_salary'])
    
    msg = await message.answer(f"{job['emoji']} Работаю **{job['name']}**...")
    
    await asyncio.sleep(2)
    
    await db.update_coins(message.from_user.id, salary)
    await db.set_work_time(message.from_user.id)
    
    await msg.edit_text(
        f"{job['emoji']} **{job['name']}**\n\n"
        f"✅ Заработано: **{format_number(salary)} VC**"
    )


# ==================== ФЕРМА ====================

@router.message(F.text.lower().in_(['ферма', 'майнинг', 'farm']))
async def farm_handler(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
        user = await db.get_user(message.from_user.id)
    
    gpus = await db.get_user_gpus(message.from_user.id)
    farm_stats = await db.get_farm_stats(message.from_user.id)
    
    total_per_hour = 0
    text = "⛏️ **ФЕРМА VIBETON**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for gpu_key, gpu_info in GPU_CONFIG.items():
        user_gpu = next((g for g in gpus if g['gpu_type'] == gpu_key), None)
        count = user_gpu['count'] if user_gpu else 0
        production = count * gpu_info['vibe_per_hour']
        total_per_hour += production
        
        price = await db.get_gpu_price(message.from_user.id, gpu_key, gpu_info['base_price'])
        
        text += f"{gpu_info['emoji']} **{gpu_info['name']}**\n"
        text += f"└ Кол-во: {count}/10 | +{production:.1f} VT/ч\n"
        text += f"└ Цена: {format_number(price)} VC\n\n"
    
    # Накопленное
    accumulated = 0
    if farm_stats and farm_stats['last_collect']:
        from datetime import datetime
        elapsed = datetime.utcnow() - farm_stats['last_collect']
        hours = elapsed.total_seconds() / 3600
        accumulated = total_per_hour * hours
    
    text += f"━━━━━━━━━━━━━━━━━━━━\n"
    text += f"⚡ Добыча: **{total_per_hour:.1f} VT/час**\n"
    text += f"💎 Накоплено: **{accumulated:.2f} VT**"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 GTX 1660", callback_data="buy_gtx1660")],
        [InlineKeyboardButton(text="🟡 RTX 3070", callback_data="buy_rtx3070")],
        [InlineKeyboardButton(text="🔴 RTX 4090", callback_data="buy_rtx4090")],
        [InlineKeyboardButton(text="💎 Собрать VT", callback_data="collect_vt")],
    ])
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith('buy_'))
async def buy_gpu_callback(callback: CallbackQuery):
    gpu_type = callback.data.replace('buy_', '')
    
    if gpu_type not in GPU_CONFIG:
        await callback.answer("❌ Ошибка!")
        return
    
    gpu = GPU_CONFIG[gpu_type]
    price = await db.get_gpu_price(callback.from_user.id, gpu_type, gpu['base_price'])
    
    success, result = await db.buy_gpu(callback.from_user.id, gpu_type, price)
    
    if success:
        await callback.answer(f"✅ Куплена {gpu['name']}!", show_alert=True)
    elif result == "max":
        await callback.answer("❌ Максимум 10 штук!", show_alert=True)
    else:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)


@router.callback_query(F.data == 'collect_vt')
async def collect_vt_callback(callback: CallbackQuery):
    gpus = await db.get_user_gpus(callback.from_user.id)
    farm_stats = await db.get_farm_stats(callback.from_user.id)
    
    total_per_hour = sum(
        (next((g['count'] for g in gpus if g['gpu_type'] == k), 0) * v['vibe_per_hour'])
        for k, v in GPU_CONFIG.items()
    )
    
    if not farm_stats or not farm_stats['last_collect']:
        await callback.answer("❌ Нечего собирать!", show_alert=True)
        return
    
    from datetime import datetime
    elapsed = datetime.utcnow() - farm_stats['last_collect']
    hours = elapsed.total_seconds() / 3600
    accumulated = total_per_hour * hours
    
    if accumulated < 0.01:
        await callback.answer("⏰ Пока нечего собирать!", show_alert=True)
        return
    
    await db.collect_farm(callback.from_user.id, accumulated)
    await callback.answer(f"✅ Собрано {accumulated:.2f} VT!", show_alert=True)


# ==================== РЫНОК ====================

@router.message(F.text.lower().in_(['рынок', 'маркет', 'market']))
async def market_handler(message: Message):
    price_data = await db.get_market_price()
    
    if not price_data:
        price = random.randint(1000, 15000)
        await db.update_market_price(price)
    else:
        from datetime import datetime, timedelta
        if datetime.utcnow() - price_data['updated_at'] > timedelta(hours=1):
            price = random.randint(1000, 15000)
            await db.update_market_price(price)
        else:
            price = price_data['price']
    
    orders = await db.get_market_orders()
    sell_orders = [o for o in orders if o['order_type'] == 'sell'][:5]
    buy_orders = [o for o in orders if o['order_type'] == 'buy'][:5]
    
    text = (
        f"🛒 **РЫНОК VIBETON**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Курс: **{format_number(price)} VC/VT**\n\n"
    )
    
    if sell_orders:
        text += "📈 **Продают:**\n"
        for o in sell_orders:
            text += f"└ {o['amount']:.2f} VT по {format_number(o['price_per_unit'])} VC\n"
        text += "\n"
    
    if buy_orders:
        text += "📉 **Покупают:**\n"
        for o in buy_orders:
            text += f"└ {o['amount']:.2f} VT по {format_number(o['price_per_unit'])} VC\n"
    
    text += "\n**Команды:**\n"
    text += "`продать 1.5 10000` - продать VT\n"
    text += "`купитьvt 1.5 10000` - купить VT"
    
    await message.answer(text)


@router.message(F.text.lower().startswith('продать'))
async def sell_vt(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 3:
        await message.answer("📈 Использование: `продать 1.5 10000`")
        return
    
    try:
        amount = float(parts[1])
        price = int(parts[2])
    except:
        await message.answer("❌ Некорректные данные!")
        return
    
    user = await db.get_user(message.from_user.id)
    if user['vibeton'] < amount:
        await message.answer("❌ Недостаточно VibeTon!")
        return
    
    success = await db.create_market_order(message.from_user.id, 'sell', amount, price)
    
    if success:
        await message.answer(f"✅ Ордер создан: {amount:.2f} VT по {format_number(price)} VC")
    else:
        await message.answer("❌ Ошибка создания ордера!")


# ==================== БАНК ====================

@router.message(F.text.lower().in_(['банк', 'bank']))
async def bank_handler(message: Message):
    user = await db.get_user(message.from_user.id)
    
    text = (
        f"🏦 **БАНК**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 На руках: **{format_number(user['coins'])} VC**\n"
        f"🏦 В банке: **{format_number(user['bank_balance'])} VC**\n\n"
        f"**Команды:**\n"
        f"`депозит 1000` - положить\n"
        f"`снять 1000` - снять\n"
        f"`перевод @user 1000` - перевести"
    )
    
    await message.answer(text)


@router.message(F.text.lower().startswith('депозит'))
async def deposit_handler(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 2:
        await message.answer("🏦 Использование: `депозит 1000`")
        return
    
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(parts[1], user['coins'])
    
    if amount <= 0:
        await message.answer("❌ Некорректная сумма!")
        return
    
    success = await db.deposit_to_bank(message.from_user.id, amount)
    
    if success:
        await message.answer(f"✅ Положено **{format_number(amount)} VC** в банк")
    else:
        await message.answer("❌ Недостаточно средств!")


@router.message(F.text.lower().startswith('снять'))
async def withdraw_handler(message: Message):
    parts = message.text.lower().split()
    if len(parts) < 2:
        await message.answer("🏦 Использование: `снять 1000`")
        return
    
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(parts[1], user['bank_balance'])
    
    if amount <= 0:
        await message.answer("❌ Некорректная сумма!")
        return
    
    success = await db.withdraw_from_bank(message.from_user.id, amount)
    
    if success:
        await message.answer(f"✅ Снято **{format_number(amount)} VC** из банка")
    else:
        await message.answer("❌ Недостаточно средств в банке!")


@router.message(F.text.lower().startswith('перевод'))
async def transfer_handler(message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("💸 Использование: `перевод @username 1000`")
        return
    
    target_username = parts[1].replace('@', '')
    
    user = await db.get_user(message.from_user.id)
    amount = parse_amount(parts[2], user['coins'])
    
    target = await db.get_user_by_username(target_username)
    
    if not target:
        await message.answer("❌ Пользователь не найден!")
        return
    
    if target['user_id'] == message.from_user.id:
        await message.answer("❌ Нельзя перевести себе!")
        return
    
    if amount <= 0:
        await message.answer("❌ Некорректная сумма!")
        return
    
    success = await db.transfer_coins(message.from_user.id, target['user_id'], amount)
    
    if success:
        await message.answer(f"✅ Переведено **{format_number(amount)} VC** → @{target_username}")
    else:
        await message.answer("❌ Недостаточно средств!")


# ==================== ТОП ====================

@router.message(F.text.lower().in_(['топ', 'top', 'рейтинг']))
async def top_handler(message: Message):
    top_coins = await db.get_top_coins(10)
    
    text = "🏆 **ТОП-10 ИГРОКОВ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    medals = ['🥇', '🥈', '🥉']
    
    for i, user in enumerate(top_coins):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = user['first_name'] or user['username'] or 'Аноним'
        text += f"{medal} {name}: **{format_number(user['coins'])} VC**\n"
    
    await message.answer(text)


# ==================== ПРОМОКОД ====================

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
            rewards.append(f"💎 {format_number(result['coins_reward'])} VC")
        if result['vibeton_reward'] > 0:
            rewards.append(f"🔮 {result['vibeton_reward']:.2f} VT")
        
        await message.answer(f"🎁 **ПРОМОКОД АКТИВИРОВАН!**\n\nПолучено: {', '.join(rewards)}")
    else:
        errors = {
            "not_found": "❌ Промокод не найден!",
            "expired": "❌ Промокод истёк!",
            "already_used": "❌ Ты уже использовал этот промокод!"
        }
        await message.answer(errors.get(result, "❌ Ошибка!"))


# ==================== ПОМОЩЬ ====================

@router.message(F.text.lower().in_(['помощь', 'help', 'команды', 'хелп', 'start']))
@router.message(CommandStart())
async def help_handler(message: Message):
    await db.create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    text = (
        "🎮 **VIBEBOT**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 `я` - профиль\n\n"
        "🎰 **Игры:**\n"
        "• `алмазы 1000`\n"
        "• `мины 1000`\n"
        "• `рулетка 1000 красное`\n"
        "• `краш 1000 2.0`\n"
        "• `футбол 1000`\n"
        "• `баскетбол 1000`\n"
        "• `боулинг 1000`\n"
        "• `дартс 1000`\n"
        "• `кости 1000 больше`\n\n"
        "💼 `работа` - работы\n"
        "⛏️ `ферма` - майнинг VT\n"
        "🛒 `рынок` - торговля VT\n"
        "🏦 `банк` - депозиты\n"
        "🏆 `топ` - рейтинг\n"
        "🎁 `промо КОД` - промокод"
    )
    
    await message.answer(text)
