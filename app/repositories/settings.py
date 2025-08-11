from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from app.models import Settings

class SettingsRepository(BaseRepository[Settings]):
    """Репозиторий для работы с настройками"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Settings)
    
    async def get_by_key(self, key: str) -> Optional[Settings]:
        """Получить настройку по ключу"""
        result = await self.session.execute(
            select(Settings).where(Settings.key == key)
        )
        return result.scalars().first()
    
    async def set_value(self, key: str, value: str) -> Settings:
        """Установить значение настройки"""
        setting = await self.get_by_key(key)
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            self.session.add(setting)
        
        await self.session.flush()
        await self.session.refresh(setting)
        return setting
    
    async def get_bool_value(self, key: str, default: bool = False) -> bool:
        """Получить булево значение настройки"""
        setting = await self.get_by_key(key)
        if not setting:
            return default
        return setting.value.lower() in ("true", "1", "yes")