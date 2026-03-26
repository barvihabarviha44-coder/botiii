import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла (для локальной разработки)
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found! Set it in environment variables")

# URL базы данных
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL not found! Set it in environment variables")

# Фикс для Railway PostgreSQL URL
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Админы
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip().isdigit()]

if not ADMIN_IDS:
    print("⚠️ Warning: No admin IDs set!")

# Эмодзи премиум
EMOJI = {
    "coin": "💎",
    "vibe": "🔮",
    "fire": "🔥",
    "star": "⭐",
    "crown": "👑",
    "rocket": "🚀",
    "diamond": "💠",
    "money": "💰",
    "bank": "🏦",
    "chart": "📊",
    "gpu": "🖥️",
    "work": "💼",
    "game": "🎰",
    "win": "🏆",
    "lose": "💔",
    "user": "👤",
    "top": "🏅",
    "help": "📖",
    "market": "🛒",
    "farm": "⛏️",
    "promo": "🎁",
    "settings": "⚙️",
    "arrow": "➤",
    "check": "✅",
    "cross": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "time": "⏰",
    "level": "📈",
    "card": "🃏",
    "dice": "🎲",
    "football": "⚽",
    "basketball": "🏀",
    "bowling": "🎳",
    "darts": "🎯",
    "crash": "📈",
    "roulette": "🎡",
    "mines": "💣",
    "gems": "💎",
}

# Видеокарты
GPU_CONFIG = {
    "gtx1660": {
        "name": "GTX 1660 Super",
        "emoji": "🟢",
        "base_price": 150000,
        "vibe_per_hour": 0.2,
        "tier": "low"
    },
    "rtx3070": {
        "name": "RTX 3070 Ti",
        "emoji": "🟡",
        "base_price": 200000,
        "vibe_per_hour": 0.4,
        "tier": "medium"
    },
    "rtx4090": {
        "name": "RTX 4090",
        "emoji": "🔴",
        "base_price": 250000,
        "vibe_per_hour": 0.6,
        "tier": "high"
    }
}

# Работы
JOBS_CONFIG = {
    "courier": {
        "name": "Курьер",
        "emoji": "🚴",
        "min_salary": 50000,
        "max_salary": 100000,
        "duration": 60,
        "description": "Доставка заказов по городу"
    },
    "programmer": {
        "name": "Программист",
        "emoji": "💻",
        "min_salary": 150000,
        "max_salary": 300000,
        "duration": 120,
        "description": "Написание кода для проектов"
    },
    "trader": {
        "name": "Трейдер",
        "emoji": "📈",
        "min_salary": 200000,
        "max_salary": 500000,
        "duration": 180,
        "description": "Торговля на бирже"
    },
    "businessman": {
        "name": "Бизнесмен",
        "emoji": "🏢",
        "min_salary": 300000,
        "max_salary": 700000,
        "duration": 240,
        "description": "Управление компанией"
    },
    "ceo": {
        "name": "CEO корпорации",
        "emoji": "👔",
        "min_salary": 500000,
        "max_salary": 1000000,
        "duration": 300,
        "description": "Руководство крупной корпорацией"
    }
}

print(f"✅ Config loaded")
print(f"📊 Bot Token: {'✅ Set' if BOT_TOKEN else '❌ Missing'}")
print(f"🗄️ Database URL: {'✅ Set' if DATABASE_URL else '❌ Missing'}")
print(f"👑 Admins: {len(ADMIN_IDS)} configured")
