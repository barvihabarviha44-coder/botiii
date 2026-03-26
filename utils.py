def format_number(num) -> str:
    """Форматирование числа"""
    if num is None:
        return "0"
    num = int(num)
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)


def format_coins(amount) -> str:
    return f"{format_number(amount)} VC"


def format_vibeton(amount) -> str:
    return f"{amount:.2f} VT"


def parse_amount(text: str, max_amount: int) -> int:
    """Парсинг суммы"""
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
    
    try:
        return int(float(text) * multiplier)
    except:
        return 0
