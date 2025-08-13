from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories import (
    UserRepository,
    ProductRepository,
    OrderRepository,
    FloristRepository,
    ConsultationRepository,
)

class UnitOfWork:
    """Unit of Work для управления транзакциями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.products = ProductRepository(session)
        self.orders = OrderRepository(session)
        self.florists = FloristRepository(session)
        self.consultations = ConsultationRepository(session)

    async def commit(self) -> None:
        """Сохранить изменения"""
        await self.session.commit()
    
    async def rollback(self) -> None:
        """Откатить изменения"""
        await self.session.rollback()
    
    async def close(self) -> None:
        """Закрыть сессию"""
        await self.session.close()

@asynccontextmanager
async def get_uow() -> AsyncGenerator[UnitOfWork, None]:
    
    """Использование:  async with get_uow() as uow: ..."""
    async for session in get_session():
        uow = UnitOfWork(session)
        try:
            yield uow
            await uow.commit()
        except Exception:
            await uow.rollback()
            raise
        finally:
            await uow.close()