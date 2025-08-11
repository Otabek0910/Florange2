from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.repositories import FloristRepository
from app.models import FloristProfile, User, RoleEnum
from app.exceptions import UserNotFoundError

class FloristService:
    """Сервис для работы с флористами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.florist_repo = FloristRepository(session)
    
    async def get_available_florists(self) -> List[dict]:
        """Получить список доступных флористов с их статусами"""
        florists = await self.florist_repo.get_active_florists()
        
        result = []
        for florist in florists:
            # Загружаем пользователя
            await self.session.refresh(florist, ['user'])
            
            # Определяем статус (онлайн если активность < 5 минут назад)
            is_online = (
                datetime.utcnow() - florist.last_seen
            ).total_seconds() < 300  # 5 минут
            
            status_text = "онлайн" if is_online else f"{self._format_last_seen(florist.last_seen)}"
            
            result.append({
                'profile': florist,
                'user': florist.user,
                'is_online': is_online,
                'status_text': status_text,
                'rating_text': f"⭐{florist.rating:.1f}" if florist.reviews_count > 0 else "⭐новый"
            })
        
        return result
    
    async def get_or_create_profile(self, user_id: int) -> FloristProfile:
        """Получить или создать профиль флориста"""
        return await self.florist_repo.create_or_get_profile(user_id)
    
    async def update_profile(self, user_id: int, bio: str = None, 
                           specialization: str = None) -> FloristProfile:
        """Обновить профиль флориста"""
        profile = await self.florist_repo.get_by_user_id(user_id)
        if not profile:
            raise UserNotFoundError(str(user_id))
        
        if bio is not None:
            profile.bio = bio
        if specialization is not None:
            profile.specialization = specialization
        
        profile.updated_at = datetime.utcnow()
        await self.session.flush()
        return profile
    
    async def update_activity(self, user_id: int) -> None:
        """Обновить активность флориста"""
        await self.florist_repo.update_last_seen(user_id)
    
    async def recalculate_rating(self, florist_id: int) -> None:
        """Пересчитать рейтинг флориста"""
        await self.florist_repo.update_rating(florist_id)
    
    def _format_last_seen(self, last_seen: datetime) -> str:
        """Форматировать время последней активности"""
        diff = datetime.utcnow() - last_seen
        
        if diff.total_seconds() < 3600:  # меньше часа
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} мин назад"
        elif diff.total_seconds() < 86400:  # меньше дня
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} ч назад"
        else:  # больше дня
            days = diff.days
            return f"{days} дн назад"