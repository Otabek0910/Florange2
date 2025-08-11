from typing import TypeVar, Generic, Optional, List, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType", bound=DeclarativeBase)

class BaseRepository(Generic[ModelType]):
    """Базовый репозиторий для CRUD операций"""
    
    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model
    
    async def get(self, id: int) -> Optional[ModelType]:
        """Получить объект по ID"""
        return await self.session.get(self.model, id)
    
    async def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """Получить все объекты"""
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return result.scalars().all()
    
    async def create(self, obj: ModelType) -> ModelType:
        """Создать объект"""
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj
    
    async def update(self, id: int, values: dict) -> Optional[ModelType]:
        """Обновить объект"""
        await self.session.execute(
            update(self.model).where(self.model.id == id).values(**values)
        )
        return await self.get(id)
    
    async def delete(self, id: int) -> bool:
        """Удалить объект"""
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0