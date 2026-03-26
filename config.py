import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///casino.db')

# Настройки игры
STARTING_BALANCE = 1000
DAILY_BONUS = 100
