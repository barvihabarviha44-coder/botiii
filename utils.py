import random
from config import LEVELS


def format_num(num) -> str:
    if num is None:
        return "0"

    num = float(num)
    negative = num < 0
    num = abs(num)

    suffixes = ["", "к", "кк", "ккк", "кккк", "ккккк"]
    idx = 0

    while num >= 1000 and idx < len(suffixes) - 1:
        num /= 1000
        idx += 1

    if idx == 0:
        value = str(int(num))
    else:
        if num >= 100:
            value = f"{num:.0f}"
        elif num >= 10:
            value = f"{num:.1f}".rstrip("0").rstrip(".")
        else:
            value = f"{num:.2f}".rstrip("0").rstrip(".")
        value = f"{value}{suffixes[idx]}"

    return f"-{value}" if negative else value


def parse_amount(text: str, max_amount: int = 0) -> int:
    if not text:
        return 0

    text = text.lower().strip()

    if text in ["все", "всё", "all", "max"]:
        return int(max_amount)
    if text in ["половина", "half"]:
        return int(max_amount // 2)

    count_k = text.count("к")
    text = text.replace("к", "").replace(",", ".")

    try:
        value = float(text)
        return int(value * (1000 ** count_k))
    except:
        return 0


def get_level(xp: int) -> int:
    level = 1
    for lvl, required in LEVELS.items():
        if xp >= required:
            level = lvl
    return level


def get_xp_for_next_level(level: int) -> int:
    return LEVELS.get(level + 1, LEVELS[max(LEVELS.keys())] + 50000)


def maybe_give_xp() -> int:
    if random.random() <= 0.25:
        return random.randint(1, 2)
    return 0
