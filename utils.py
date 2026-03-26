from config import EMOJI
import random

def format_number(num):
    """Форматирование чисел с разделителями"""
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(int(num))

def format_coins(amount):
    """Форматирование монет"""
    return f"{format_number(amount)} {EMOJI['coin']} VC"

def format_vibeton(amount):
    """Форматирование VibeTon"""
    return f"{amount:.2f} {EMOJI['vibe']} VT"

def format_time(seconds):
    """Форматирование времени"""
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins} мин {secs} сек"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours} ч {mins} мин"

def parse_amount(text: str, max_amount: int) -> int:
    """Парсинг суммы из текста"""
    text = text.lower().strip()
    
    if text in ['все', 'всё', 'all', 'max']:
        return max_amount
    
    if text in ['половина', 'half', '50%']:
        return max_amount // 2
    
    multiplier = 1
    if text.endswith('k') or text.endswith('к'):
        multiplier = 1000
        text = text[:-1]
    elif text.endswith('m') or text.endswith('м'):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith('b') or text.endswith('б'):
        multiplier = 1_000_000_000
        text = text[:-1]
    
    try:
        return int(float(text) * multiplier)
    except:
        return 0

def get_roulette_color(number: int) -> str:
    """Получение цвета числа в рулетке"""
    if number == 0:
        return "green"
    red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    return "red" if number in red_numbers else "black"

def generate_crash_multiplier() -> float:
    """Генерация множителя для краш игры"""
    # Используем экспоненциальное распределение
    r = random.random()
    if r < 0.01:  # 1% шанс на большой множитель
        return round(random.uniform(100, 505), 2)
    elif r < 0.1:  # 9% шанс на средний
        return round(random.uniform(10, 100), 2)
    elif r < 0.5:  # 40% шанс
        return round(random.uniform(2, 10), 2)
    else:  # 50% шанс на низкий
        return round(random.uniform(1.01, 2), 2)

def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Создание прогресс-бара"""
    filled = int(length * current / total)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    percent = int(100 * current / total)
    return f"[{bar}] {percent}%"
