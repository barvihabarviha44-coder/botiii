import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import config
from database import (
    get_or_create_user, 
    update_user_stats, 
    claim_daily_bonus,
    get_user
)
from games import Games

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Хранилище для временных данных пользователей
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    get_or_create_user(user.id, user.username)
    
    keyboard = [
        [InlineKeyboardButton("🎮 Играть", callback_data='games')],
        [InlineKeyboardButton("👤 Профиль", callback_data='profile')],
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data='daily')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🎰 Добро пожаловать в Казино-бот, {user.first_name}!

💰 Начальный баланс: {config.STARTING_BALANCE} монет
🎁 Ежедневный бонус: {config.DAILY_BONUS} монет

Выбери действие:
    """
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль"""
    query = update.callback_query
    await query.answer()
    
    user = get_user(query.from_user.id)
    
    win_rate = 0
    if user.games_played > 0:
        win_rate = (user.total_wins / user.games_played) * 100
    
    profile_text = f"""
👤 Профиль игрока

🆔 ID: {user.user_id}
👤 Юзернейм: @{user.username or 'не указан'}

💰 Баланс: {user.balance} монет
🎮 Игр сыграно: {user.games_played}
✅ Побед: {user.total_wins}
❌ Поражений: {user.total_losses}
📊 Винрейт: {win_rate:.1f}%

📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}
    """
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(profile_text, reply_markup=reply_markup)

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный бонус"""
    query = update.callback_query
    await query.answer()
    
    success, result = claim_daily_bonus(query.from_user.id)
    
    if success:
        text = f"🎁 Вы получили ежедневный бонус!\n\n💰 +{result} монет"
    else:
        text = f"⏰ Бонус уже получен!\n\nСледующий бонус через: {result}"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню игр"""
    query = update.callback_query
    await query.answer()
    
    user = get_user(query.from_user.id)
    
    keyboard = [
        [InlineKeyboardButton("🪙 Монетка", callback_data='game_coin')],
        [InlineKeyboardButton("🎲 Кости", callback_data='game_dice')],
        [InlineKeyboardButton("🎰 Слоты", callback_data='game_slots')],
        [InlineKeyboardButton("🔴 Рулетка", callback_data='game_roulette')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"🎮 Выберите игру\n\n💰 Ваш баланс: {user.balance} монет"
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def game_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра: Монетка"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("50 монет", callback_data='coin_bet_50')],
        [InlineKeyboardButton("100 монет", callback_data='coin_bet_100')],
        [InlineKeyboardButton("250 монет", callback_data='coin_bet_250')],
        [InlineKeyboardButton("500 монет", callback_data='coin_bet_500')],
        [InlineKeyboardButton("◀️ Назад", callback_data='games')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
🪙 Орёл или Решка

Выберите ставку:
Выигрыш: x2
    """
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def coin_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор ставки для монетки"""
    query = update.callback_query
    await query.answer()
    
    bet = int(query.data.split('_')[-1])
    user = get_user(query.from_user.id)
    
    if user.balance < bet:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    # Сохраняем ставку
    user_data[query.from_user.id] = {'game': 'coin', 'bet': bet}
    
    keyboard = [
        [
            InlineKeyboardButton("🪙 Орёл", callback_data='coin_heads'),
            InlineKeyboardButton("🪙 Решка", callback_data='coin_tails')
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data='game_coin')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"🪙 Ставка: {bet} монет\n\nВыберите сторону:"
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def coin_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Играть в монетку"""
    query = update.callback_query
    await query.answer()
    
    choice = query.data.split('_')[-1]
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.answer("❌ Ошибка! Начните заново.", show_alert=True)
        return
    
    bet = user_data[user_id]['bet']
    result = Games.coin_flip(bet, choice)
    
    update_user_stats(user_id, result['won'], result['amount'])
    
    if result['won']:
        text = f"""
✅ Победа!

Ваш выбор: {result['choice']}
Результат: {result['result']}

💰 Выигрыш: +{result['amount']} монет
        """
    else:
        text = f"""
❌ Проигрыш!

Ваш выбор: {result['choice']}
Результат: {result['result']}

💸 Проигрыш: -{result['amount']} монет
        """
    
    user = get_user(user_id)
    text += f"\n💰 Текущий баланс: {user.balance} монет"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Играть ещё", callback_data='game_coin')],
        [InlineKeyboardButton("◀️ В меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    del user_data[user_id]
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def game_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра: Кости"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("50 монет", callback_data='dice_bet_50')],
        [InlineKeyboardButton("100 монет", callback_data='dice_bet_100')],
        [InlineKeyboardButton("250 монет", callback_data='dice_bet_250')],
        [InlineKeyboardButton("500 монет", callback_data='dice_bet_500')],
        [InlineKeyboardButton("◀️ Назад", callback_data='games')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
🎲 Кости

Правила:
6 = x3
5 = x2
4 = x1.5
1-3 = проигрыш

Выберите ставку:
    """
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def dice_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Играть в кости"""
    query = update.callback_query
    await query.answer()
    
    bet = int(query.data.split('_')[-1])
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user.balance < bet:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    result = Games.dice(bet)
    
    update_user_stats(user_id, result['won'], result['amount'])
    
    if result['won']:
        text = f"""
✅ Победа!

{result['result']}
Множитель: {result['multiplier']}

💰 Выигрыш: +{result['amount']} монет
        """
    else:
        text = f"""
❌ Проигрыш!

{result['result']}

💸 Проигрыш: -{result['amount']} монет
        """
    
    user = get_user(user_id)
    text += f"\n💰 Текущий баланс: {user.balance} монет"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Играть ещё", callback_data='game_dice')],
        [InlineKeyboardButton("◀️ В меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def game_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра: Слоты"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("50 монет", callback_data='slots_bet_50')],
        [InlineKeyboardButton("100 монет", callback_data='slots_bet_100')],
        [InlineKeyboardButton("250 монет", callback_data='slots_bet_250')],
        [InlineKeyboardButton("500 монет", callback_data='slots_bet_500')],
        [InlineKeyboardButton("◀️ Назад", callback_data='games')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
🎰 Слоты

Множители:
7️⃣7️⃣7️⃣ = x10
💎💎💎 = x7
🍇🍇🍇 = x5
🍊🍊🍊 = x3
🍋🍋🍋 = x2
🍒🍒🍒 = x1.5

Две одинаковых = x0.5

Выберите ставку:
    """
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def slots_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Играть в слоты"""
    query = update.callback_query
    await query.answer()
    
    bet = int(query.data.split('_')[-1])
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user.balance < bet:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    result = Games.slots(bet)
    
    update_user_stats(user_id, result['won'], result['amount'])
    
    if result['won']:
        text = f"""
✅ Победа!

🎰 [ {result['result']} ]

Множитель: {result['multiplier']}
💰 Выигрыш: +{result['amount']} монет
        """
    else:
        text = f"""
❌ Проигрыш!

🎰 [ {result['result']} ]

💸 Проигрыш: -{result['amount']} монет
        """
    
    user = get_user(user_id)
    text += f"\n💰 Текущий баланс: {user.balance} монет"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Играть ещё", callback_data='game_slots')],
        [InlineKeyboardButton("◀️ В меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def game_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра: Рулетка"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("50 монет", callback_data='roulette_bet_50')],
        [InlineKeyboardButton("100 монет", callback_data='roulette_bet_100')],
        [InlineKeyboardButton("250 монет", callback_data='roulette_bet_250')],
        [InlineKeyboardButton("500 монет", callback_data='roulette_bet_500')],
        [InlineKeyboardButton("◀️ Назад", callback_data='games')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
🔴 Рулетка

Правила:
🔴 Красное = x2
⚫ Чёрное = x2
🟢 Зелёное (0) = x35

Выберите ставку:
    """
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def roulette_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор ставки для рулетки"""
    query = update.callback_query
    await query.answer()
    
    bet = int(query.data.split('_')[-1])
    user = get_user(query.from_user.id)
    
    if user.balance < bet:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    # Сохраняем ставку
    user_data[query.from_user.id] = {'game': 'roulette', 'bet': bet}
    
    keyboard = [
        [
            InlineKeyboardButton("🔴 Красное", callback_data='roulette_red'),
            InlineKeyboardButton("⚫ Чёрное", callback_data='roulette_black')
        ],
        [InlineKeyboardButton("🟢 Зелёное (0)", callback_data='roulette_green')],
        [InlineKeyboardButton("◀️ Назад", callback_data='game_roulette')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"🔴 Ставка: {bet} монет\n\nВыберите цвет:"
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def roulette_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Играть в рулетку"""
    query = update.callback_query
    await query.answer()
    
    choice = query.data.split('_')[-1]
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.answer("❌ Ошибка! Начните заново.", show_alert=True)
        return
    
    bet = user_data[user_id]['bet']
    result = Games.roulette(bet, choice)
    
    update_user_stats(user_id, result['won'], result['amount'])
    
    color_names = {'red': '🔴 Красное', 'black': '⚫ Чёрное', 'green': '🟢 Зелёное'}
    
    if result['won']:
        text = f"""
✅ Победа!

Ваш выбор: {color_names[choice]}
Результат: {result['result']}

Множитель: {result['multiplier']}
💰 Выигрыш: +{result['amount']} монет
        """
    else:
        text = f"""
❌ Проигрыш!

Ваш выбор: {color_names[choice]}
Результат: {result['result']}

💸 Проигрыш: -{result['amount']} монет
        """
    
    user = get_user(user_id)
    text += f"\n💰 Текущий баланс: {user.balance} монет"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Играть ещё", callback_data='game_roulette')],
        [InlineKeyboardButton("◀️ В меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    del user_data[user_id]
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в главное меню"""
    query = update.callback_query
    await query.answer()
    
    user = get_user(query.from_user.id)
    
    keyboard = [
        [InlineKeyboardButton("🎮 Играть", callback_data='games')],
        [InlineKeyboardButton("👤 Профиль", callback_data='profile')],
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data='daily')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""
🎰 Главное меню

💰 Ваш баланс: {user.balance} монет

Выберите действие:
    """
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех кнопок"""
    query = update.callback_query
    
    handlers = {
        'profile': profile,
        'daily': daily_bonus,
        'games': games_menu,
        'game_coin': game_coin,
        'game_dice': game_dice,
        'game_slots': game_slots,
        'game_roulette': game_roulette,
        'back_to_menu': back_to_menu,
    }
    
    # Обработка ставок для монетки
    if query.data.startswith('coin_bet_'):
        await coin_bet(update, context)
        return
    
    # Обработка игры в монетку
    if query.data in ['coin_heads', 'coin_tails']:
        await coin_play(update, context)
        return
    
    # Обработка игры в кости
    if query.data.startswith('dice_bet_'):
        await dice_play(update, context)
        return
    
    # Обработка игры в слоты
    if query.data.startswith('slots_bet_'):
        await slots_play(update, context)
        return
    
    # Обработка ставок для рулетки
    if query.data.startswith('roulette_bet_'):
        await roulette_bet(update, context)
        return
    
    # Обработка игры в рулетку
    if query.data in ['roulette_red', 'roulette_black', 'roulette_green']:
        await roulette_play(update, context)
        return
    
    # Остальные обработчики
    handler = handlers.get(query.data)
    if handler:
        await handler(update, context)

def main():
    """Запуск бота"""
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
