import random
from config import LEVELS


def format_number(num) -> str:
    """Форматирование: 1.98к, 10кк, 100ккк"""
    if num is None:
        return "0"
    
    num = int(num)
    
    if num < 1000:
        return str(num)
    elif num < 1000000:
        # Тысячи: к
        val = num / 1000
        if val == int(val):
            return f"{int(val)}к"
        else:
            return f"{val:.2f}к".rstrip('0').rstrip('.')  + "к" if not f"{val:.2f}".rstrip('0').rstrip('.').endswith('к') else f"{val:.2f}".rstrip('0').rstrip('.')
    elif num < 1000000000:
        # Миллионы: кк
        val = num / 1000000
        if val == int(val):
            return f"{int(val)}кк"
        else:
            formatted = f"{val:.2f}".rstrip('0').rstrip('.')
            return f"{formatted}кк"
    elif num < 1000000000000:
        # Миллиарды: ккк
        val = num / 1000000000
        if val == int(val):
            return f"{int(val)}ккк"
        else:
            formatted = f"{val:.2f}".rstrip('0').rstrip('.')
            return f"{formatted}ккк"
    else:
        # Триллионы: кккк
        val = num / 1000000000000
        if val == int(val):
            return f"{int(val)}кккк"
        else:
            formatted = f"{val:.2f}".rstrip('0').rstrip('.')
            return f"{formatted}кккк"


def format_num(num) -> str:
    """Простое форматирование"""
    if num is None:
        return "0"
    num = int(num)
    if num < 1000:
        return str(num)
    elif num < 1000000:
        v = num / 1000
        return f"{v:.1f}к".replace('.0к', 'к')
    elif num < 1000000000:
        v = num / 1000000
        return f"{v:.1f}кк".replace('.0кк', 'кк')
    elif num < 1000000000000:
        v = num / 1000000000
        return f"{v:.1f}ккк".replace('.0ккк', 'ккк')
    else:
        v = num / 1000000000000
        return f"{v:.1f}кккк".replace('.0кккк', 'кккк')


def parse_amount(text: str, max_amount: int) -> int:
    """Парсинг суммы: 100к, 1кк, все"""
    text = text.lower().strip()
    
    if text in ['все', 'всё', 'all', 'max']:
        return max_amount
    if text in ['половина', 'half']:
        return max_amount // 2
    
    # Считаем количество 'к'
    k_count = text.count('к') + text.count('k')
    text_clean = text.replace('к', '').replace('k', '')
    
    try:
        value = float(text_clean.replace(',', '.'))
        multiplier = 1000 ** k_count
        return int(value * multiplier)
    except:
        return 0


def get_level(xp: int) -> int:
    """Получить уровень по XP"""
    level = 1
    for lvl, required_xp in LEVELS.items():
        if xp >= required_xp:
            level = lvl
    return level


def get_xp_for_next_level(current_level: int) -> int:
    """XP для следующего уровня"""
    next_level = current_level + 1
    if next_level in LEVELS:
        return LEVELS[next_level]
    return LEVELS.get(current_level, 0) + 50000


def maybe_give_xp() -> int:
    """Шанс 25% дать 1-2 XP"""
    if random.random() < 0.25:
        return random.randint(1, 2)
    return 0
