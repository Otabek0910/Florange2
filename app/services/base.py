from sqlalchemy.ext.asyncio import AsyncSession
from typing import TypeVar, Generic

T = TypeVar('T')

class BaseService(Generic[T]):
    """Базовый сервис с управлением сессией"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._should_commit = False
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and self._should_commit:
            await self.session.commit()
        elif exc_type is not None:
            await self.session.rollback()
    
    def commit_on_success(self):
        """Пометить для автоматического commit"""
        self._should_commit = True
        return self