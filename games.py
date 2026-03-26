import random

class Games:
    
    @staticmethod
    def coin_flip(bet, choice):
        """
        Орел или решка
        choice: 'heads' или 'tails'
        """
        result = random.choice(['heads', 'tails'])
        won = result == choice
        
        emoji_map = {'heads': '🪙 Орёл', 'tails': '🪙 Решка'}
        
        return {
            'won': won,
            'result': emoji_map[result],
            'choice': emoji_map[choice],
            'amount': bet if won else bet
        }
    
    @staticmethod
    def dice(bet):
        """
        Кости (1-6)
        6 = x3
        5 = x2
        4 = x1.5
        1-3 = проигрыш
        """
        result = random.randint(1, 6)
        
        multipliers = {
            6: 3,
            5: 2,
            4: 1.5,
            3: 0,
            2: 0,
            1: 0
        }
        
        multiplier = multipliers[result]
        won = multiplier > 0
        amount = int(bet * multiplier) if won else bet
        
        return {
            'won': won,
            'result': f'🎲 Выпало: {result}',
            'amount': amount,
            'multiplier': f'x{multiplier}' if won else 'Проигрыш'
        }
    
    @staticmethod
    def slots(bet):
        """
        Слоты 3x3
        """
        symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
        weights = [30, 25, 20, 15, 7, 3]
        
        result = random.choices(symbols, weights=weights, k=3)
        
        # Проверка выигрыша
        if result[0] == result[1] == result[2]:
            if result[0] == '7️⃣':
                multiplier = 10
            elif result[0] == '💎':
                multiplier = 7
            elif result[0] == '🍇':
                multiplier = 5
            elif result[0] == '🍊':
                multiplier = 3
            elif result[0] == '🍋':
                multiplier = 2
            else:  # 🍒
                multiplier = 1.5
            won = True
        elif result[0] == result[1] or result[1] == result[2]:
            multiplier = 0.5
            won = True
        else:
            multiplier = 0
            won = False
        
        amount = int(bet * multiplier) if won else bet
        
        return {
            'won': won,
            'result': ' '.join(result),
            'amount': amount,
            'multiplier': f'x{multiplier}' if won else 'Проигрыш'
        }
    
    @staticmethod
    def roulette(bet, choice):
        """
        Рулетка
        choice: 'red', 'black', 'green', или число 0-36
        """
        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        black_numbers = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
        
        result_number = random.randint(0, 36)
        
        if result_number == 0:
            result_color = 'green'
            color_emoji = '🟢'
        elif result_number in red_numbers:
            result_color = 'red'
            color_emoji = '🔴'
        else:
            result_color = 'black'
            color_emoji = '⚫'
        
        # Проверка выигрыша
        if choice.isdigit():
            choice_num = int(choice)
            won = choice_num == result_number
            multiplier = 35 if won else 0
        else:
            won = choice == result_color
            if result_color == 'green' and won:
                multiplier = 35
            else:
                multiplier = 2 if won else 0
        
        amount = int(bet * multiplier) if won else bet
        
        return {
            'won': won,
            'result': f'{color_emoji} {result_number}',
            'amount': amount,
            'multiplier': f'x{multiplier}' if won else 'Проигрыш'
        }
