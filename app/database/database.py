# app/database/database.py - заменить создание engine
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.config import config
from sqlalchemy import text

# Использовать конфигурацию вместо прямого чтения env
DATABASE_URL = config.DATABASE_URL

print(f"🔗 Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'локальная'}")

# Убираем глобальный engine - создаем при первом использовании
_engine = None
_session_factory = None

def get_engine():
    """Получить или создать engine"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            DATABASE_URL, 
            echo=False, 
            future=True,
            pool_pre_ping=True,  # Проверка соединений
            pool_recycle=300     # Переподключение каждые 5 минут
        )
    return _engine

def get_session_factory():
    """Получить фабрику сессий"""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), 
            expire_on_commit=False, 
            class_=AsyncSession
        )
    return _session_factory

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session

async def init_db():
    """Инициализация базы данных с проверками"""
    try:
        print("🔗 Проверяем подключение к БД...")
        
        engine = get_engine()
        
        # Проверка подключения
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✅ Подключение к БД успешно")
        
        # Создание таблиц
        print("📋 Создаем таблицы...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ База данных инициализирована")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        # Сбрасываем engine при ошибке
        global _engine, _session_factory
        if _engine:
            await _engine.dispose()
            _engine = None
            _session_factory = None
        raise

async def close_db():
    """Закрыть соединения с БД"""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None