import random
import asyncio
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import EMOJI
from database import db
from utils import format_coins, format_vibeton

async def get_current_price():
    """Получение текущей цены VibeTon"""
    price_data = await db.get_market_price()
    
    if not price_data or (datetime.utcnow() - price_data['updated_at']) > timedelta(hours=1):
        # Обновляем цену
        new_price = random.randint(1000, 15000)
        await db.update_market_price(new_price)
        return new_price
    
    return price_data['price']

async def get_market_info() -> str:
    """Информация о рынке"""
    current_price = await get_current_price()
    orders = await db.get_market_orders()
    
    sell_orders = [o for o in orders if o['order_type'] == 'sell']
    buy_orders = [o for o in orders if o['order_type'] == 'buy']
    
    text = (
        f"{EMOJI['market']} **РЫНОК VIBETON**\n"
        f"{'═' * 25}\n\n"
        f"📊 **Текущий курс бота:**\n"
        f"   1 VT = {format_coins(current_price)}\n\n"
        f"{'─' * 25}\n"
        f"📈 **Ордера на продажу ({len(sell_orders)}):**\n"
    )
    
    for order in sell_orders[:5]:
        text += f"   • {order['amount']:.2f} VT по {format_coins(order['price_per_unit'])}/VT\n"
    
    text += f"\n📉 **Ордера на покупку ({len(buy_orders)}):**\n"
    for order in buy_orders[:5]:
        text += f"   • {order['amount']:.2f} VT по {format_coins(order['price_per_unit'])}/VT\n"
    
    return text

def get_market_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура рынка"""
    keyboard = [
        [
            InlineKeyboardButton(text="📈 Продать", callback_data="market_sell"),
            InlineKeyboardButton(text="📉 Купить", callback_data="market_buy")
        ],
        [InlineKeyboardButton(text="📋 Мои ордера", callback_data="market_my_orders")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="market_refresh")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
