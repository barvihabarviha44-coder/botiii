import asyncpg
import asyncio
import json
from datetime import datetime, timedelta
from config import DATABASE_URL

class Database:
    def __init__(self):
        self.pool = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL)
        await self.create_tables()
    
    async def create_tables(self):
        async with self.pool.acquire() as conn:
            # Пользователи
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    coins BIGINT DEFAULT 10000,
                    vibeton DOUBLE PRECISION DEFAULT 0,
                    bank_balance BIGINT DEFAULT 0,
                    total_games INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    total_earned BIGINT DEFAULT 0,
                    total_lost BIGINT DEFAULT 0,
                    is_banned BOOLEAN DEFAULT FALSE,
                    ban_reason TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_work TIMESTAMP,
                    last_daily TIMESTAMP,
                    last_active TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Видеокарты пользователей
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_gpus (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    gpu_type TEXT,
                    count INTEGER DEFAULT 0,
                    current_price INTEGER,
                    purchased_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, gpu_type)
                )
            ''')
            
            # Статистика фермы
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS farm_stats (
                    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                    last_collect TIMESTAMP DEFAULT NOW(),
                    total_mined DOUBLE PRECISION DEFAULT 0,
                    total_gpus_bought INTEGER DEFAULT 0
                )
            ''')
            
            # Ордера на рынке
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS market_orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    order_type TEXT CHECK (order_type IN ('buy', 'sell')),
                    amount DOUBLE PRECISION,
                    price_per_unit INTEGER,
                    created_at TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE,
                    completed_at TIMESTAMP
                )
            ''')
            
            # История цен на рынке
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS market_price (
                    id SERIAL PRIMARY KEY,
                    price INTEGER,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Промокоды
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS promocodes (
                    code TEXT PRIMARY KEY,
                    coins_reward BIGINT DEFAULT 0,
                    vibeton_reward DOUBLE PRECISION DEFAULT 0,
                    max_uses INTEGER DEFAULT 1,
                    current_uses INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by BIGINT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP
                )
            ''')
            
            # Использования промокодов
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS promo_uses (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    code TEXT REFERENCES promocodes(code) ON DELETE CASCADE,
                    used_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, code)
                )
            ''')
            
            # Транзакции
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    from_user BIGINT,
                    to_user BIGINT,
                    amount BIGINT,
                    currency TEXT CHECK (currency IN ('VC', 'VT')),
                    type TEXT CHECK (type IN ('transfer', 'game_win', 'game_loss', 'work', 'farm', 'market', 'admin', 'promo')),
                    description TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Игровые сессии
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS game_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    game_type TEXT CHECK (game_type IN ('diamond', 'mines', 'roulette', 'crash', 'dice', 'football', 'basketball', 'bowling', 'darts')),
                    bet BIGINT,
                    state JSONB,
                    is_active BOOLEAN DEFAULT TRUE,
                    result TEXT,
                    winnings BIGINT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    finished_at TIMESTAMP
                )
            ''')
            
            # История работ
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS work_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    job_type TEXT,
                    salary INTEGER,
                    worked_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Логи действий админов
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id SERIAL PRIMARY KEY,
                    admin_id BIGINT,
                    action TEXT,
                    target_user BIGINT,
                    details JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Статистика игр
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS game_stats (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    game_type TEXT,
                    total_played INTEGER DEFAULT 0,
                    total_won INTEGER DEFAULT 0,
                    total_earned BIGINT DEFAULT 0,
                    total_lost BIGINT DEFAULT 0,
                    best_win BIGINT DEFAULT 0,
                    worst_loss BIGINT DEFAULT 0,
                    UNIQUE(user_id, game_type)
                )
            ''')
            
            # Рефералы (на будущее)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id SERIAL PRIMARY KEY,
                    referrer_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    referred_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    reward_given BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(referred_id)
                )
            ''')
            
            # Ежедневные награды
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_rewards (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    streak INTEGER DEFAULT 0,
                    last_claim TIMESTAMP,
                    total_claimed INTEGER DEFAULT 0
                )
            ''')
            
            # Достижения
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS achievements (
                    id SERIAL PRIMARY KEY,
                    code TEXT UNIQUE,
                    name TEXT,
                    description TEXT,
                    reward_coins INTEGER DEFAULT 0,
                    reward_vt DOUBLE PRECISION DEFAULT 0,
                    icon TEXT
                )
            ''')
            
            # Достижения пользователей
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_achievements (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    achievement_code TEXT REFERENCES achievements(code) ON DELETE CASCADE,
                    unlocked_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, achievement_code)
                )
            ''')
            
            # Индексы для оптимизации
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_coins ON users(coins DESC)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_vibeton ON users(vibeton DESC)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_market_orders_active ON market_orders(is_active, order_type)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(from_user, to_user)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_game_sessions_user ON game_sessions(user_id, is_active)')

    # ==================== USER METHODS ====================
    
    async def get_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            # Обновляем последнюю активность
            await conn.execute(
                'UPDATE users SET last_active = NOW() WHERE user_id = $1',
                user_id
            )
            return await conn.fetchrow(
                'SELECT * FROM users WHERE user_id = $1', user_id
            )
    
    async def create_user(self, user_id: int, username: str, first_name: str):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET
                username = $2, first_name = $3, last_active = NOW()
            ''', user_id, username, first_name)
            
            await conn.execute('''
                INSERT INTO farm_stats (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING
            ''', user_id)
            
            await conn.execute('''
                INSERT INTO daily_rewards (user_id)
                VALUES ($1)
                ON CONFLICT DO NOTHING
            ''', user_id)
    
    async def update_coins(self, user_id: int, amount: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET coins = coins + $2 WHERE user_id = $1',
                user_id, amount
            )
    
    async def update_vibeton(self, user_id: int, amount: float):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET vibeton = vibeton + $2 WHERE user_id = $1',
                user_id, amount
            )
    
    async def update_stats(self, user_id: int, won: bool, amount: int):
        async with self.pool.acquire() as conn:
            if won:
                await conn.execute('''
                    UPDATE users SET 
                    total_games = total_games + 1,
                    total_wins = total_wins + 1,
                    total_earned = total_earned + $2
                    WHERE user_id = $1
                ''', user_id, amount)
            else:
                await conn.execute('''
                    UPDATE users SET 
                    total_games = total_games + 1,
                    total_lost = total_lost + $2
                    WHERE user_id = $1
                ''', user_id, amount)
    
    async def get_balance(self, user_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT coins, vibeton, bank_balance FROM users WHERE user_id = $1',
                user_id
            )
            return row
    
    async def set_balance(self, user_id: int, coins: int = None, vibeton: float = None):
        async with self.pool.acquire() as conn:
            if coins is not None:
                await conn.execute(
                    'UPDATE users SET coins = $2 WHERE user_id = $1',
                    user_id, coins
                )
            if vibeton is not None:
                await conn.execute(
                    'UPDATE users SET vibeton = $2 WHERE user_id = $1',
                    user_id, vibeton
                )
    
    async def get_user_by_username(self, username: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM users WHERE LOWER(username) = LOWER($1)', username
            )
    
    # ==================== BANK METHODS ====================
    
    async def deposit_to_bank(self, user_id: int, amount: int):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                'SELECT coins FROM users WHERE user_id = $1', user_id
            )
            if result['coins'] >= amount:
                await conn.execute('''
                    UPDATE users SET 
                    coins = coins - $2,
                    bank_balance = bank_balance + $2
                    WHERE user_id = $1
                ''', user_id, amount)
                
                await self.add_transaction(user_id, user_id, amount, 'VC', 'transfer', 'Депозит в банк')
                return True
            return False
    
    async def withdraw_from_bank(self, user_id: int, amount: int):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                'SELECT bank_balance FROM users WHERE user_id = $1', user_id
            )
            if result['bank_balance'] >= amount:
                await conn.execute('''
                    UPDATE users SET 
                    coins = coins + $2,
                    bank_balance = bank_balance - $2
                    WHERE user_id = $1
                ''', user_id, amount)
                
                await self.add_transaction(user_id, user_id, amount, 'VC', 'transfer', 'Снятие из банка')
                return True
            return False
    
    async def transfer_coins(self, from_user: int, to_user: int, amount: int):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                'SELECT coins FROM users WHERE user_id = $1', from_user
            )
            if result['coins'] >= amount:
                await conn.execute(
                    'UPDATE users SET coins = coins - $2 WHERE user_id = $1',
                    from_user, amount
                )
                await conn.execute(
                    'UPDATE users SET coins = coins + $2 WHERE user_id = $1',
                    to_user, amount
                )
                
                await self.add_transaction(from_user, to_user, amount, 'VC', 'transfer', 'Перевод между игроками')
                return True
            return False
    
    async def set_bank_balance(self, user_id: int, amount: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET bank_balance = $2 WHERE user_id = $1',
                user_id, amount
            )
    
    # ==================== GPU/FARM METHODS ====================
    
    async def get_user_gpus(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM user_gpus WHERE user_id = $1', user_id
            )
    
    async def buy_gpu(self, user_id: int, gpu_type: str, price: int):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                'SELECT coins FROM users WHERE user_id = $1', user_id
            )
            if result['coins'] >= price:
                await conn.execute(
                    'UPDATE users SET coins = coins - $2 WHERE user_id = $1',
                    user_id, price
                )
                
                existing = await conn.fetchrow('''
                    SELECT count, current_price FROM user_gpus 
                    WHERE user_id = $1 AND gpu_type = $2
                ''', user_id, gpu_type)
                
                new_price = int(price * 1.2)
                
                if existing:
                    if existing['count'] >= 10:
                        await conn.execute(
                            'UPDATE users SET coins = coins + $2 WHERE user_id = $1',
                            user_id, price
                        )
                        return False, "max"
                    await conn.execute('''
                        UPDATE user_gpus SET count = count + 1, current_price = $3
                        WHERE user_id = $1 AND gpu_type = $2
                    ''', user_id, gpu_type, new_price)
                else:
                    await conn.execute('''
                        INSERT INTO user_gpus (user_id, gpu_type, count, current_price)
                        VALUES ($1, $2, 1, $3)
                    ''', user_id, gpu_type, new_price)
                
                await conn.execute('''
                    UPDATE farm_stats SET total_gpus_bought = total_gpus_bought + 1
                    WHERE user_id = $1
                ''', user_id)
                
                await self.add_transaction(user_id, None, price, 'VC', 'farm', f'Покупка видеокарты {gpu_type}')
                
                return True, new_price
            return False, "no_money"
    
    async def get_gpu_price(self, user_id: int, gpu_type: str, base_price: int):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow('''
                SELECT current_price FROM user_gpus 
                WHERE user_id = $1 AND gpu_type = $2
            ''', user_id, gpu_type)
            return result['current_price'] if result else base_price
    
    async def get_farm_stats(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM farm_stats WHERE user_id = $1', user_id
            )
    
    async def collect_farm(self, user_id: int, amount: float):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE farm_stats SET 
                last_collect = NOW(),
                total_mined = total_mined + $2
                WHERE user_id = $1
            ''', user_id, amount)
            
            await conn.execute(
                'UPDATE users SET vibeton = vibeton + $2 WHERE user_id = $1',
                user_id, amount
            )
            
            await self.add_transaction(user_id, user_id, int(amount * 1000), 'VT', 'farm', 'Сбор VibeTon с фермы')
    
    # ==================== MARKET METHODS ====================
    
    async def get_market_price(self):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                'SELECT price, updated_at FROM market_price ORDER BY id DESC LIMIT 1'
            )
            return result
    
    async def update_market_price(self, price: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO market_price (price) VALUES ($1)', price
            )
    
    async def create_market_order(self, user_id: int, order_type: str, amount: float, price: int):
        async with self.pool.acquire() as conn:
            if order_type == 'sell':
                result = await conn.fetchrow(
                    'SELECT vibeton FROM users WHERE user_id = $1', user_id
                )
                if result['vibeton'] < amount:
                    return False
                await conn.execute(
                    'UPDATE users SET vibeton = vibeton - $2 WHERE user_id = $1',
                    user_id, amount
                )
            
            await conn.execute('''
                INSERT INTO market_orders (user_id, order_type, amount, price_per_unit)
                VALUES ($1, $2, $3, $4)
            ''', user_id, order_type, amount, price)
            return True
    
    async def get_market_orders(self, order_type: str = None):
        async with self.pool.acquire() as conn:
            if order_type:
                return await conn.fetch('''
                    SELECT mo.*, u.username, u.first_name FROM market_orders mo
                    JOIN users u ON mo.user_id = u.user_id
                    WHERE order_type = $1 AND is_active = TRUE
                    ORDER BY 
                        CASE WHEN order_type = 'sell' THEN price_per_unit END ASC,
                        CASE WHEN order_type = 'buy' THEN price_per_unit END DESC
                ''', order_type)
            return await conn.fetch('''
                SELECT mo.*, u.username, u.first_name FROM market_orders mo
                JOIN users u ON mo.user_id = u.user_id
                WHERE is_active = TRUE
                ORDER BY created_at DESC
            ''')
    
    async def get_user_market_orders(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM market_orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT 20',
                user_id
            )
    
    async def buy_from_market(self, buyer_id: int, order_id: int):
        async with self.pool.acquire() as conn:
            order = await conn.fetchrow(
                'SELECT * FROM market_orders WHERE id = $1 AND is_active = TRUE',
                order_id
            )
            if not order:
                return False, "not_found"
            
            total_cost = int(order['amount'] * order['price_per_unit'])
            buyer = await conn.fetchrow(
                'SELECT coins FROM users WHERE user_id = $1', buyer_id
            )
            
            if buyer['coins'] < total_cost:
                return False, "no_money"
            
            # Списываем деньги у покупателя
            await conn.execute(
                'UPDATE users SET coins = coins - $2 WHERE user_id = $1',
                buyer_id, total_cost
            )
            
            # Начисляем VibeTon покупателю
            await conn.execute(
                'UPDATE users SET vibeton = vibeton + $2 WHERE user_id = $1',
                buyer_id, order['amount']
            )
            
            # Начисляем деньги продавцу
            await conn.execute(
                'UPDATE users SET coins = coins + $2 WHERE user_id = $1',
                order['user_id'], total_cost
            )
            
            # Закрываем ордер
            await conn.execute(
                'UPDATE market_orders SET is_active = FALSE, completed_at = NOW() WHERE id = $1',
                order_id
            )
            
            await self.add_transaction(buyer_id, order['user_id'], total_cost, 'VC', 'market', f'Покупка {order["amount"]} VT')
            
            return True, order
    
    async def cancel_market_order(self, user_id: int, order_id: int):
        async with self.pool.acquire() as conn:
            order = await conn.fetchrow(
                'SELECT * FROM market_orders WHERE id = $1 AND user_id = $2 AND is_active = TRUE',
                order_id, user_id
            )
            
            if not order:
                return False
            
            # Возвращаем VT если это ордер на продажу
            if order['order_type'] == 'sell':
                await conn.execute(
                    'UPDATE users SET vibeton = vibeton + $2 WHERE user_id = $1',
                    user_id, order['amount']
                )
            
            await conn.execute(
                'UPDATE market_orders SET is_active = FALSE WHERE id = $1',
                order_id
            )
            
            return True
    
    async def clear_all_market_orders(self):
        async with self.pool.acquire() as conn:
            # Возвращаем VT продавцам
            orders = await conn.fetch(
                "SELECT user_id, amount FROM market_orders WHERE order_type = 'sell' AND is_active = TRUE"
            )
            for order in orders:
                await conn.execute(
                    'UPDATE users SET vibeton = vibeton + $2 WHERE user_id = $1',
                    order['user_id'], order['amount']
                )
            
            await conn.execute('UPDATE market_orders SET is_active = FALSE')
    
    # ==================== TOP METHODS ====================
    
    async def get_top_coins(self, limit: int = 10):
        async with self.pool.acquire() as conn:
            return await conn.fetch('''
                SELECT user_id, username, first_name, coins, is_banned
                FROM users 
                WHERE is_banned = FALSE
                ORDER BY coins DESC 
                LIMIT $1
            ''', limit)
    
    async def get_top_vibeton(self, limit: int = 10):
        async with self.pool.acquire() as conn:
            return await conn.fetch('''
                SELECT user_id, username, first_name, vibeton 
                FROM users 
                WHERE is_banned = FALSE
                ORDER BY vibeton DESC 
                LIMIT $1
            ''', limit)
    
    # ==================== PROMO METHODS ====================
    
    async def create_promo(self, code: str, coins: int, vibeton: float, max_uses: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO promocodes (code, coins_reward, vibeton_reward, max_uses)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (code) DO UPDATE SET
                coins_reward = $2, vibeton_reward = $3, max_uses = $4, is_active = TRUE
            ''', code, coins, vibeton, max_uses)
    
    async def use_promo(self, user_id: int, code: str):
        async with self.pool.acquire() as conn:
            promo = await conn.fetchrow(
                'SELECT * FROM promocodes WHERE code = $1 AND is_active = TRUE',
                code
            )
            if not promo:
                return False, "not_found"
            
            if promo['current_uses'] >= promo['max_uses']:
                return False, "expired"
            
            used = await conn.fetchrow(
                'SELECT * FROM promo_uses WHERE user_id = $1 AND code = $2',
                user_id, code
            )
            if used:
                return False, "already_used"
            
            await conn.execute('''
                INSERT INTO promo_uses (user_id, code) VALUES ($1, $2)
            ''', user_id, code)
            
            await conn.execute('''
                UPDATE promocodes SET current_uses = current_uses + 1 WHERE code = $1
            ''', code)
            
            if promo['coins_reward'] > 0:
                await conn.execute(
                    'UPDATE users SET coins = coins + $2 WHERE user_id = $1',
                    user_id, promo['coins_reward']
                )
            
            if promo['vibeton_reward'] > 0:
                await conn.execute(
                    'UPDATE users SET vibeton = vibeton + $2 WHERE user_id = $1',
                    user_id, promo['vibeton_reward']
                )
            
            await self.add_transaction(user_id, None, promo['coins_reward'], 'VC', 'promo', f'Промокод {code}')
            
            return True, promo
    
    async def get_all_promos(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM promocodes ORDER BY created_at DESC'
            )
    
    async def get_promo(self, code: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM promocodes WHERE code = $1', code
            )
    
    async def delete_promo(self, code: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE promocodes SET is_active = FALSE WHERE code = $1', code
            )
    
    # ==================== WORK METHODS ====================
    
    async def can_work(self, user_id: int):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                'SELECT last_work FROM users WHERE user_id = $1', user_id
            )
            if not result['last_work']:
                return True
            return datetime.utcnow() - result['last_work'] > timedelta(minutes=30)
    
    async def set_work_time(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET last_work = NOW() WHERE user_id = $1', user_id
            )
    
    async def get_work_cooldown(self, user_id: int):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                'SELECT last_work FROM users WHERE user_id = $1', user_id
            )
            if not result['last_work']:
                return 0
            elapsed = datetime.utcnow() - result['last_work']
            remaining = timedelta(minutes=30) - elapsed
            return max(0, int(remaining.total_seconds()))
    
    async def add_work_history(self, user_id: int, job_type: str, salary: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO work_history (user_id, job_type, salary)
                VALUES ($1, $2, $3)
            ''', user_id, job_type, salary)
    
    # ==================== GAME SESSION METHODS ====================
    
    async def create_game_session(self, user_id: int, game_type: str, bet: int, state: dict):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow('''
                INSERT INTO game_sessions (user_id, game_type, bet, state)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            ''', user_id, game_type, bet, json.dumps(state))
            return result['id']
    
    async def get_game_session(self, user_id: int, game_type: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow('''
                SELECT * FROM game_sessions 
                WHERE user_id = $1 AND game_type = $2 AND is_active = TRUE
                ORDER BY created_at DESC LIMIT 1
            ''', user_id, game_type)
    
    async def update_game_session(self, session_id: int, state: dict, is_active: bool = True):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE game_sessions SET state = $2, is_active = $3 WHERE id = $1
            ''', session_id, json.dumps(state), is_active)
    
    async def close_game_session(self, session_id: int, result: str = None, winnings: int = 0):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE game_sessions 
                SET is_active = FALSE, finished_at = NOW(), result = $2, winnings = $3
                WHERE id = $1
            ''', session_id, result, winnings)
    
    async def update_game_stats(self, user_id: int, game_type: str, won: bool, amount: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO game_stats (user_id, game_type, total_played, total_won, total_earned, total_lost, best_win, worst_loss)
                VALUES ($1, $2, 1, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id, game_type) DO UPDATE SET
                    total_played = game_stats.total_played + 1,
                    total_won = game_stats.total_won + $3,
                    total_earned = game_stats.total_earned + $4,
                    total_lost = game_stats.total_lost + $5,
                    best_win = GREATEST(game_stats.best_win, $6),
                    worst_loss = GREATEST(game_stats.worst_loss, $7)
            ''', user_id, game_type, 
                1 if won else 0, 
                amount if won else 0, 
                amount if not won else 0,
                amount if won else 0,
                amount if not won else 0
            )
    
    # ==================== ADMIN METHODS ====================
    
    async def ban_user(self, user_id: int, ban: bool = True, reason: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET is_banned = $2, ban_reason = $3 WHERE user_id = $1',
                user_id, ban, reason
            )
    
    async def get_banned_users(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch('''
                SELECT user_id, username, first_name, ban_reason, created_at 
                FROM users 
                WHERE is_banned = TRUE
                ORDER BY created_at DESC
                LIMIT 50
            ''')
    
    async def get_all_users(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT user_id FROM users WHERE is_banned = FALSE'
            )
    
    async def get_all_users_count(self):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow('SELECT COUNT(*) as count FROM users')
            return result['count']
    
    async def reset_user_data(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE users SET 
                    coins = 10000,
                    vibeton = 0,
                    bank_balance = 0,
                    total_games = 0,
                    total_wins = 0,
                    total_earned = 0,
                    total_lost = 0
                WHERE user_id = $1
            ''', user_id)
            
            await conn.execute('DELETE FROM user_gpus WHERE user_id = $1', user_id)
            await conn.execute('DELETE FROM market_orders WHERE user_id = $1', user_id)
            await conn.execute('DELETE FROM game_sessions WHERE user_id = $1', user_id)
            await conn.execute('DELETE FROM game_stats WHERE user_id = $1', user_id)
            
            await conn.execute('''
                UPDATE farm_stats SET 
                    last_collect = NOW(),
                    total_mined = 0,
                    total_gpus_bought = 0
                WHERE user_id = $1
            ''', user_id)
    
    async def add_admin_log(self, admin_id: int, action: str, target_user: int = None, details: dict = None):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO admin_logs (admin_id, action, target_user, details)
                VALUES ($1, $2, $3, $4)
            ''', admin_id, action, target_user, json.dumps(details) if details else None)
    
    async def get_global_stats(self):
        async with self.pool.acquire() as conn:
            users = await conn.fetchrow('''
                SELECT 
                    COUNT(*) as total_users,
                    COUNT(*) FILTER (WHERE is_banned = TRUE) as banned_users,
                    COALESCE(SUM(coins), 0) as total_coins,
                    COALESCE(SUM(vibeton), 0) as total_vibeton,
                    COALESCE(SUM(bank_balance), 0) as total_bank,
                    COALESCE(SUM(total_games), 0) as total_games,
                    COALESCE(SUM(total_earned), 0) as total_won,
                    COALESCE(SUM(total_lost), 0) as total_lost
                FROM users
            ''')
            
            active_24h = await conn.fetchval('''
                SELECT COUNT(*) FROM users 
                WHERE last_active > NOW() - INTERVAL '24 hours'
            ''')
            
            total_gpus = await conn.fetchval('''
                SELECT COALESCE(SUM(count), 0) FROM user_gpus
            ''')
            
            total_mined = await conn.fetchval('''
                SELECT COALESCE(SUM(total_mined), 0) FROM farm_stats
            ''')
            
            active_orders = await conn.fetchval('''
                SELECT COUNT(*) FROM market_orders WHERE is_active = TRUE
            ''')
            
            price = await self.get_market_price()
            current_price = price['price'] if price else 5000
            
            total_transactions = await conn.fetchval('''
                SELECT COUNT(*) FROM transactions
            ''')
            
            total_promos = await conn.fetchval('''
                SELECT COUNT(*) FROM promocodes WHERE is_active = TRUE
            ''')
            
            return {
                'total_users': users['total_users'],
                'banned_users': users['banned_users'],
                'active_24h': active_24h or 0,
                'total_coins': users['total_coins'] or 0,
                'total_vibeton': users['total_vibeton'] or 0,
                'total_bank': users['total_bank'] or 0,
                'total_games': users['total_games'] or 0,
                'total_won': users['total_won'] or 0,
                'total_lost': users['total_lost'] or 0,
                'total_gpus': total_gpus or 0,
                'total_mined': total_mined or 0,
                'active_orders': active_orders or 0,
                'current_price': current_price,
                'total_transactions': total_transactions or 0,
                'total_promos': total_promos or 0
            }
    
    # ==================== TRANSACTION METHODS ====================
    
    async def add_transaction(self, from_user: int, to_user: int, amount: int, currency: str, trans_type: str, description: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO transactions (from_user, to_user, amount, currency, type, description)
                VALUES ($1, $2, $3, $4, $5, $6)
            ''', from_user, to_user, amount, currency, trans_type, description)
    
    async def get_user_transactions(self, user_id: int, limit: int = 20):
        async with self.pool.acquire() as conn:
            return await conn.fetch('''
                SELECT * FROM transactions 
                WHERE from_user = $1 OR to_user = $1
                ORDER BY created_at DESC
                LIMIT $2
            ''', user_id, limit)
    
    # ==================== DAILY REWARDS ====================
    
    async def claim_daily(self, user_id: int):
        async with self.pool.acquire() as conn:
            daily = await conn.fetchrow(
                'SELECT * FROM daily_rewards WHERE user_id = $1', user_id
            )
            
            if not daily:
                await conn.execute(
                    'INSERT INTO daily_rewards (user_id, streak, last_claim, total_claimed) VALUES ($1, 1, NOW(), 1)',
                    user_id
                )
                return 1, 1000  # День 1, награда 1000
            
            if daily['last_claim']:
                time_since = datetime.utcnow() - daily['last_claim']
                
                if time_since < timedelta(hours=20):
                    # Слишком рано
                    return 0, 0
                elif time_since > timedelta(hours=48):
                    # Streak сброшен
                    new_streak = 1
                else:
                    # Продолжение streak
                    new_streak = daily['streak'] + 1
            else:
                new_streak = 1
            
            # Награда увеличивается с каждым днем
            reward = min(1000 * new_streak, 7000)  # Максимум 7000 на 7 день
            
            await conn.execute('''
                UPDATE daily_rewards 
                SET streak = $2, last_claim = NOW(), total_claimed = total_claimed + 1
                WHERE user_id = $1
            ''', user_id, new_streak)
            
            await conn.execute(
                'UPDATE users SET coins = coins + $2 WHERE user_id = $1',
                user_id, reward
            )
            
            return new_streak, reward
    
    async def get_daily_info(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM daily_rewards WHERE user_id = $1', user_id
            )

db = Database()
