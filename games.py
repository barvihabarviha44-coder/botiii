import random
import asyncio
import json
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from config import EMOJI
from utils import format_coins, parse_amount

class DiamondGame:
    """Игра Алмазы - угадай где алмаз на 16 уровнях"""
    
    @staticmethod
    def create_field(level: int):
        """Создание игрового поля для уровня"""
        size = min(2 + level // 4, 5)  # От 2x2 до 5x5
        cells = size * size
        diamond_pos = random.randint(0, cells - 1)
        return {
            'size': size,
            'diamond': diamond_pos,
            'opened': [],
            'level': level
        }
    
    @staticmethod
    def get_keyboard(state: dict, session_id: int):
        """Генерация клавиатуры"""
        size = state['size']
        keyboard = []
        
        for row in range(size):
            row_buttons = []
            for col in range(size):
                cell_id = row * size + col
                if cell_id in state['opened']:
                    if cell_id == state['diamond']:
                        text = "💎"
                    else:
                        text = "✖️"
                else:
                    text = "❓"
                callback = f"diamond_{session_id}_{cell_id}"
                row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback))
            keyboard.append(row_buttons)
        
        # Кнопка забрать
        if state['level'] > 1:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"💰 Забрать x{state['level'] * 0.5:.1f}", 
                    callback_data=f"diamond_{session_id}_cashout"
                )
            ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

class MinesGame:
    """Игра Мины"""
    
    @staticmethod
    def create_field(mines_count: int = 5):
        """Создание поля 5x5 с минами"""
        cells = list(range(25))
        mines = random.sample(cells, mines_count)
        return {
            'mines': mines,
            'opened': [],
            'mines_count': mines_count,
            'multiplier': 1.0
        }
    
    @staticmethod
    def calculate_multiplier(opened_count: int, mines_count: int) -> float:
        """Расчет множителя"""
        safe_cells = 25 - mines_count
        if opened_count == 0:
            return 1.0
        # Базовая формула для расчета множителя
        mult = 1.0
        for i in range(opened_count):
            mult *= (safe_cells - i) / (25 - mines_count - i)
        return round(1 / mult, 2)
    
    @staticmethod
    def get_keyboard(state: dict, session_id: int, game_over: bool = False):
        """Генерация клавиатуры"""
        keyboard = []
        
        for row in range(5):
            row_buttons = []
            for col in range(5):
                cell_id = row * 5 + col
                if cell_id in state['opened']:
                    if cell_id in state['mines']:
                        text = "💣"
                    else:
                        text = "💎"
                elif game_over and cell_id in state['mines']:
                    text = "💣"
                else:
                    text = "🟦"
                
                if game_over or cell_id in state['opened']:
                    callback = "mines_disabled"
                else:
                    callback = f"mines_{session_id}_{cell_id}"
                
                row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback))
            keyboard.append(row_buttons)
        
        if not game_over and len(state['opened']) > 0:
            mult = MinesGame.calculate_multiplier(len(state['opened']), state['mines_count'])
            keyboard.append([
                InlineKeyboardButton(
                    text=f"💰 Забрать x{mult}", 
                    callback_data=f"mines_{session_id}_cashout"
                )
            ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)


class RouletteGame:
    """Рулетка"""
    
    RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    BLACK_NUMBERS = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
    
    @staticmethod
    async def play(user_id: int, bet: int, bet_type: str) -> tuple:
        """
        Игра в рулетку
        bet_type: число 0-36, 'red', 'black', '1-12', '13-24', '25-36'
        """
        result = random.randint(0, 36)
        result_color = "green" if result == 0 else ("red" if result in RouletteGame.RED_NUMBERS else "black")
        
        won = False
        multiplier = 0
        
        # Проверка выигрыша
        if bet_type.isdigit():
            bet_num = int(bet_type)
            if bet_num == result:
                won = True
                multiplier = 36 if bet_num == 0 else 35
        elif bet_type in ['red', 'красное', 'кра']:
            if result_color == 'red':
                won = True
                multiplier = 2
        elif bet_type in ['black', 'черное', 'чер']:
            if result_color == 'black':
                won = True
                multiplier = 2
        elif bet_type == '1-12':
            if 1 <= result <= 12:
                won = True
                multiplier = 3
        elif bet_type == '13-24':
            if 13 <= result <= 24:
                won = True
                multiplier = 3
        elif bet_type == '25-36':
            if 25 <= result <= 36:
                won = True
                multiplier = 3
        
        winnings = bet * multiplier if won else 0
        
        # Обновляем баланс
        if won:
            await db.update_coins(user_id, winnings - bet)
            await db.update_stats(user_id, True, winnings)
        else:
            await db.update_coins(user_id, -bet)
            await db.update_stats(user_id, False, bet)
        
        return result, result_color, won, winnings, multiplier


class CrashGame:
    """Краш игра"""
    
    @staticmethod
    async def play(bot: Bot, chat_id: int, user_id: int, bet: int, cashout_at: float):
        """Игра Краш с визуализацией"""
        from utils import generate_crash_multiplier
        
        crash_point = generate_crash_multiplier()
        
        # Анимация роста
        msg = await bot.send_message(
            chat_id,
            f"🚀 **КРАШ**\n\n"
            f"📈 Множитель: `1.00x`\n"
            f"💰 Ставка: {format_coins(bet)}\n"
            f"🎯 Вывод на: `{cashout_at}x`"
        )
        
        current = 1.0
        step = 0.1
        
        while current < crash_point:
            current = min(current + step, crash_point)
            step *= 1.1  # Ускорение
            
            if current >= cashout_at:
                # Успешный вывод
                winnings = int(bet * cashout_at)
                await db.update_coins(user_id, winnings - bet)
                await db.update_stats(user_id, True, winnings)
                
                await msg.edit_text(
                    f"🚀 **КРАШ**\n\n"
                    f"📈 Множитель: `{current:.2f}x`\n"
                    f"✅ **ВЫВЕДЕНО НА {cashout_at}x!**\n\n"
                    f"💰 Выигрыш: {format_coins(winnings)}"
                )
                return True, winnings
            
            try:
                await msg.edit_text(
                    f"🚀 **КРАШ**\n\n"
                    f"📈 Множитель: `{current:.2f}x`\n"
                    f"💰 Ставка: {format_coins(bet)}\n"
                    f"🎯 Вывод на: `{cashout_at}x`"
                )
            except:
                pass
            
            await asyncio.sleep(0.3)
        
        # Краш
        await db.update_coins(user_id, -bet)
        await db.update_stats(user_id, False, bet)
        
        await msg.edit_text(
            f"💥 **КРАШ!**\n\n"
            f"📉 Крашнуло на: `{crash_point}x`\n"
            f"🎯 Твой вывод: `{cashout_at}x`\n\n"
            f"💔 Проигрыш: {format_coins(bet)}"
        )
        return False, bet


class DiceGames:
    """Игры с анимациями Telegram"""
    
    @staticmethod
    async def play_football(bot: Bot, chat_id: int, user_id: int, bet: int):
        """Футбол ⚽"""
        msg = await bot.send_dice(chat_id, emoji="⚽")
        value = msg.dice.value  # 1-5, где 3,4,5 - гол
        
        await asyncio.sleep(4)
        
        is_goal = value >= 3
        multiplier = 1.8 if is_goal else 3.7
        
        if is_goal:
            winnings = int(bet * multiplier)
            await db.update_coins(user_id, winnings - bet)
            await db.update_stats(user_id, True, winnings)
            text = f"⚽ **ГОЛ!**\n\n🏆 Множитель: x{multiplier}\n💰 Выигрыш: {format_coins(winnings)}"
        else:
            # Мимо - тоже выигрыш с большим множителем
            winnings = int(bet * multiplier)
            await db.update_coins(user_id, winnings - bet)
            await db.update_stats(user_id, True, winnings)
            text = f"⚽ **МИМО!**\n\n🎯 Множитель: x{multiplier}\n💰 Выигрыш: {format_coins(winnings)}"
        
        await bot.send_message(chat_id, text)
    
    @staticmethod
    async def play_basketball(bot: Bot, chat_id: int, user_id: int, bet: int):
        """Баскетбол 🏀"""
        msg = await bot.send_dice(chat_id, emoji="🏀")
        value = msg.dice.value  # 1-5, где 4,5 - попадание
        
        await asyncio.sleep(4)
        
        is_goal = value >= 4
        multiplier = 3.8 if is_goal else 1.9
        
        winnings = int(bet * multiplier)
        await db.update_coins(user_id, winnings - bet)
        await db.update_stats(user_id, True, winnings)
        
        if is_goal:
            text = f"🏀 **ПОПАЛ!**\n\n🏆 Множитель: x{multiplier}\n💰 Выигрыш: {format_coins(winnings)}"
        else:
            text = f"🏀 **МИМО!**\n\n🎯 Множитель: x{multiplier}\n💰 Выигрыш: {format_coins(winnings)}"
        
        await bot.send_message(chat_id, text)
    
    @staticmethod
    async def play_bowling(bot: Bot, chat_id: int, user_id: int, bet: int):
        """Боулинг 🎳"""
        msg = await bot.send_dice(chat_id, emoji="🎳")
        value = msg.dice.value  # 1-6
        
        await asyncio.sleep(4)
        
        is_strike = value == 6
        multiplier = 5.3 if is_strike else 1.9
        
        winnings = int(bet * multiplier)
        await db.update_coins(user_id, winnings - bet)
        await db.update_stats(user_id, True, winnings)
        
        if is_strike:
            text = f"🎳 **СТРАЙК!**\n\n🏆 Множитель: x{multiplier}\n💰 Выигрыш: {format_coins(winnings)}"
        else:
            text = f"🎳 **Сбито: {value} кеглей**\n\n🎯 Множитель: x{multiplier}\n💰 Выигрыш: {format_coins(winnings)}"
        
        await bot.send_message(chat_id, text)
    
    @staticmethod
    async def play_darts(bot: Bot, chat_id: int, user_id: int, bet: int):
        """Дартс 🎯"""
        msg = await bot.send_dice(chat_id, emoji="🎯")
        value = msg.dice.value  # 1-6, где 6 - центр
        
        await asyncio.sleep(4)
        
        if value == 6:  # Центр
            multiplier = 5.8
            result = "ЦЕНТР!"
        elif value == 1:  # Мимо
            multiplier = 5.8
            result = "МИМО (редкость!)"
        else:  # Белое или красное
            multiplier = 1.9
            result = "Попадание!"
        
        winnings = int(bet * multiplier)
        await db.update_coins(user_id, winnings - bet)
        await db.update_stats(user_id, True, winnings)
        
        text = f"🎯 **{result}**\n\n🏆 Множитель: x{multiplier}\n💰 Выигрыш: {format_coins(winnings)}"
        await bot.send_message(chat_id, text)
    
    @staticmethod
    async def play_dice(bot: Bot, chat_id: int, user_id: int, bet: int, prediction: str):
        """Кости 🎲🎲"""
        msg1 = await bot.send_dice(chat_id, emoji="🎲")
        await asyncio.sleep(1)
        msg2 = await bot.send_dice(chat_id, emoji="🎲")
        
        await asyncio.sleep(3)
        
        total = msg1.dice.value + msg2.dice.value
        
        won = False
        if prediction == 'больше' and total > 7:
            won = True
            multiplier = 2.3
        elif prediction == 'меньше' and total < 7:
            won = True
            multiplier = 2.3
        elif prediction == 'ровно' and total == 7:
            won = True
            multiplier = 5.8
        
        if won:
            winnings = int(bet * multiplier)
            await db.update_coins(user_id, winnings - bet)
            await db.update_stats(user_id, True, winnings)
            text = f"🎲 **Сумма: {total}**\n\n✅ Угадал!\n🏆 Множитель: x{multiplier}\n💰 Выигрыш: {format_coins(winnings)}"
        else:
            await db.update_coins(user_id, -bet)
            await db.update_stats(user_id, False, bet)
            text = f"🎲 **Сумма: {total}**\n\n❌ Не угадал!\n💔 Проигрыш: {format_coins(bet)}"
        
        await bot.send_message(chat_id, text)
