import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip().isdigit()]

# Видеокарты
GPU_CONFIG = {
    "gtx1660": {
        "name": "GTX 1660 Super",
        "emoji": "🟢",
        "base_price": 150000,
        "vibe_per_hour": 0.2,
    },
    "rtx3070": {
        "name": "RTX 3070 Ti", 
        "emoji": "🟡",
        "base_price": 200000,
        "vibe_per_hour": 0.4,
    },
    "rtx4090": {
        "name": "RTX 4090",
        "emoji": "🔴", 
        "base_price": 250000,
        "vibe_per_hour": 0.6,
    }
}

# Работы
JOBS_CONFIG = {
    "courier": {"name": "Курьер", "emoji": "🚴", "min_salary": 50000, "max_salary": 100000},
    "programmer": {"name": "Программист", "emoji": "💻", "min_salary": 150000, "max_salary": 300000},
    "trader": {"name": "Трейдер", "emoji": "📈", "min_salary": 200000, "max_salary": 500000},
    "businessman": {"name": "Бизнесмен", "emoji": "🏢", "min_salary": 300000, "max_salary": 700000},
    "ceo": {"name": "CEO", "emoji": "👔", "min_salary": 500000, "max_salary": 1000000},
}

# Уровни
LEVELS = {
    1: 0, 2: 100, 3: 250, 4: 500, 5: 1000,
    6: 2000, 7: 3500, 8: 5500, 9: 8000, 10: 12000,
    11: 17000, 12: 23000, 13: 30000, 14: 40000, 15: 55000,
    16: 75000, 17: 100000, 18: 130000, 19: 170000, 20: 220000,
}

# Налог президента
PRESIDENT_TAX = 0.0001  # 0.01%
