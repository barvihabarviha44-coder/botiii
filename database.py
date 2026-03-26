import asyncpg
import asyncio
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
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_work TIMESTAMP,
                    last_daily TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_gpus (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    gpu_type TEXT,
                    count INTEGER DEFAULT 0,
                    current_price INTEGER,
                    UNIQUE(user_id, gpu_type)
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS farm_stats (
                    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
                    last_collect TIMESTAMP DEFAULT NOW(),
                    total_mined DOUBLE PRECISION DEFAULT 0
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS market_orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    order_type TEXT,
                    amount DOUBLE PRECISION,
                    price_per_unit INTEGER,
                    created_at TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS market_price (
                    id SERIAL PRIMARY KEY,
                    price INTEGER,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS promocodes (
                    code TEXT PRIMARY KEY,
                    coins_reward BIGINT DEFAULT 0,
                    vibeton_reward DOUBLE PRECISION DEFAULT 0,
                    max_uses INTEGER DEFAULT 1,
                    current_uses INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS promo_uses (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    code TEXT REFERENCES promocodes(code),
                    used_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, code)
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    from_user BIGINT,
                    to_user BIGINT,
                    amount BIGINT,
                    currency TEXT,
                    type TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS game_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    game_type TEXT,
                    bet BIGINT,
                    state JSONB,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')

    # User methods
    async def get_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM users WHERE user_id = $1', user_id
            )
    
    async def create_user(self, user_id: int, username: str, first_name: str):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET
                username = $2, first_name = $3
            ''', user_id, username, first_name)
            
            await conn.execute('''
                INSERT INTO farm_stats (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING
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
    
    # Bank methods
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
                await conn.execute('''
                    INSERT INTO transactions (from_user, to_user, amount, currency, type)
                    VALUES ($1, $2, $3, 'VC', 'transfer')
                ''', from_user, to_user, amount)
                return True
            return False
    
    # GPU/Farm methods
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
    
    # Market methods
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
                    SELECT mo.*, u.username FROM market_orders mo
                    JOIN users u ON mo.user_id = u.user_id
                    WHERE order_type = $1 AND is_active = TRUE
                    ORDER BY price_per_unit ASC
                ''', order_type)
            return await conn.fetch('''
                SELECT mo.*, u.username FROM market_orders mo
                JOIN users u ON mo.user_id = u.user_id
                WHERE is_active = TRUE
                ORDER BY created_at DESC
            ''')
    
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
                'UPDATE market_orders SET is_active = FALSE WHERE id = $1',
                order_id
            )
            
            return True, order
    
    # Top methods
    async def get_top_coins(self, limit: int = 10):
        async with self.pool.acquire() as conn:
            return await conn.fetch('''
                SELECT user_id, username, first_name, coins 
                FROM users WHERE is_banned = FALSE
                ORDER BY coins DESC LIMIT $1
            ''', limit)
    
    async def get_top_vibeton(self, limit: int = 10):
        async with self.pool.acquire() as conn:
            return await conn.fetch('''
                SELECT user_id, username, first_name, vibeton 
                FROM users WHERE is_banned = FALSE
                ORDER BY vibeton DESC LIMIT $1
            ''', limit)
    
    # Promo methods
    async def create_promo(self, code: str, coins: int, vibeton: float, max_uses: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO promocodes (code, coins_reward, vibeton_reward, max_uses)
                VALUES ($1, $2, $3, $4)
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
            
            return True, promo
    
    # Work methods
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
    
    # Admin methods
    async def ban_user(self, user_id: int, ban: bool = True):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET is_banned = $2 WHERE user_id = $1',
                user_id, ban
            )
    
    async def get_all_users_count(self):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow('SELECT COUNT(*) as count FROM users')
            return result['count']
    
    async def get_user_by_username(self, username: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM users WHERE username = $1', username
            )
    
    # Game sessions
    async def create_game_session(self, user_id: int, game_type: str, bet: int, state: dict):
        async with self.pool.acquire() as conn:
            import json
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
            import json
            await conn.execute('''
                UPDATE game_sessions SET state = $2, is_active = $3 WHERE id = $1
            ''', session_id, json.dumps(state), is_active)
    
    async def close_game_session(self, session_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE game_sessions SET is_active = FALSE WHERE id = $1',
                session_id
            )

db = Database()
