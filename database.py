from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import config

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    balance = Column(Integer, default=config.STARTING_BALANCE)
    total_wins = Column(Integer, default=0)
    total_losses = Column(Integer, default=0)
    games_played = Column(Integer, default=0)
    last_daily = Column(DateTime, default=None)
    created_at = Column(DateTime, default=datetime.now)

# Подготовка URL базы данных для Railway
database_url = config.DATABASE_URL
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_session():
    return Session()

def get_or_create_user(user_id, username=None):
    session = get_session()
    user = session.query(User).filter_by(user_id=user_id).first()
    
    if not user:
        user = User(user_id=user_id, username=username)
        session.add(user)
        session.commit()
    
    session.refresh(user)
    session.close()
    return user

def update_user_balance(user_id, amount):
    session = get_session()
    user = session.query(User).filter_by(user_id=user_id).first()
    user.balance += amount
    session.commit()
    session.close()

def update_user_stats(user_id, won, amount):
    session = get_session()
    user = session.query(User).filter_by(user_id=user_id).first()
    user.games_played += 1
    if won:
        user.total_wins += 1
        user.balance += amount
    else:
        user.total_losses += 1
        user.balance -= amount
    session.commit()
    session.close()

def claim_daily_bonus(user_id):
    session = get_session()
    user = session.query(User).filter_by(user_id=user_id).first()
    
    now = datetime.now()
    if user.last_daily is None or (now - user.last_daily) >= timedelta(hours=24):
        user.balance += config.DAILY_BONUS
        user.last_daily = now
        session.commit()
        session.close()
        return True, config.DAILY_BONUS
    else:
        time_left = timedelta(hours=24) - (now - user.last_daily)
        hours = time_left.seconds // 3600
        minutes = (time_left.seconds % 3600) // 60
        session.close()
        return False, f"{hours}ч {minutes}м"

def get_user(user_id):
    session = get_session()
    user = session.query(User).filter_by(user_id=user_id).first()
    session.close()
    return user
