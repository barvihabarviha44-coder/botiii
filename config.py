import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

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

JOBS_CONFIG = {
    "janitor": {"name": "Дворник", "emoji": "🧹", "min_salary": 50000, "max_salary": 80000, "level": 1},
    "courier": {"name": "Курьер", "emoji": "🚴", "min_salary": 70000, "max_salary": 120000, "level": 2},
    "waiter": {"name": "Официант", "emoji": "🍽️", "min_salary": 100000, "max_salary": 180000, "level": 3},
    "seller": {"name": "Продавец", "emoji": "🛍️", "min_salary": 150000, "max_salary": 250000, "level": 4},
    "manager": {"name": "Менеджер", "emoji": "📋", "min_salary": 250000, "max_salary": 400000, "level": 5},
    "programmer": {"name": "Программист", "emoji": "💻", "min_salary": 350000, "max_salary": 600000, "level": 7},
    "trader": {"name": "Трейдер", "emoji": "📈", "min_salary": 500000, "max_salary": 900000, "level": 10},
    "lawyer": {"name": "Юрист", "emoji": "⚖️", "min_salary": 700000, "max_salary": 1200000, "level": 12},
    "businessman": {"name": "Бизнесмен", "emoji": "🏢", "min_salary": 1000000, "max_salary": 1800000, "level": 15},
    "ceo": {"name": "CEO", "emoji": "👔", "min_salary": 1500000, "max_salary": 3000000, "level": 20},
}

LEVELS = {
    1: 0,
    2: 20,
    3: 50,
    4: 90,
    5: 140,
    6: 200,
    7: 280,
    8: 380,
    9: 500,
    10: 650,
    11: 850,
    12: 1100,
    13: 1400,
    14: 1750,
    15: 2200,
    16: 2800,
    17: 3500,
    18: 4300,
    19: 5200,
    20: 6500,
}

PRESIDENT_TAX = 0.0001
