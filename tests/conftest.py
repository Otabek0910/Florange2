import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.database import get_session

@pytest.fixture
async def test_db():
    """Тестовая база данных"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async def get_test_session():
        async with async_session() as session:
            yield session
    
    # Подменяем зависимость
    get_session = get_test_session
    yield get_test_session
    
    await engine.dispose()

@pytest.fixture
def event_loop():
    """Event loop для тестов"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()