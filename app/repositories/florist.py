from typing import List, Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from .base import BaseRepository
from app.models import FloristProfile, User, RoleEnum, FloristReview

class FloristRepository(BaseRepository[FloristProfile]):
    """Репозиторий для работы с флористами"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, FloristProfile)
    
    async def get_by_user_id(self, user_id: int) -> Optional[FloristProfile]:
        """Получить профиль флориста по user_id"""
        result = await self.session.execute(
            select(FloristProfile).where(FloristProfile.user_id == user_id)
        )
        return result.scalars().first()
    
    async def get_active_florists(self) -> List[FloristProfile]:
        """Получить активных флористов с пользователями"""
        result = await self.session.execute(
            select(FloristProfile)
            .join(User)
            .where(
                and_(
                    FloristProfile.is_active == True,
                    User.role == RoleEnum.florist
                )
            )
            .order_by(FloristProfile.rating.desc(), FloristProfile.last_seen.desc())
        )
        return result.scalars().all()
    
    async def update_last_seen(self, user_id: int) -> None:
        """Обновить время последней активности флориста"""
        profile = await self.get_by_user_id(user_id)
        if profile:
            profile.last_seen = datetime.utcnow()
            await self.session.flush()
    
    async def update_rating(self, florist_id: int) -> None:
        """Пересчитать рейтинг флориста на основе отзывов"""
        # Получаем средний рейтинг и количество отзывов
        result = await self.session.execute(
            select(
                func.avg(FloristReview.rating).label('avg_rating'),
                func.count(FloristReview.id).label('reviews_count')
            )
            .where(FloristReview.florist_id == florist_id)
        )
        
        stats = result.first()
        avg_rating = float(stats.avg_rating) if stats.avg_rating else 0.0
        reviews_count = stats.reviews_count or 0
        
        # Обновляем профиль флориста
        profile = await self.get_by_user_id(florist_id)
        if profile:
            profile.rating = round(avg_rating, 2)
            profile.reviews_count = reviews_count
            await self.session.flush()
    
    async def create_or_get_profile(self, user_id: int) -> FloristProfile:
        """Создать или получить профиль флориста"""
        profile = await self.get_by_user_id(user_id)
        if not profile:
            profile = FloristProfile(
                user_id=user_id,
                bio="",
                specialization="Флорист",
                is_active=True
            )
            profile = await self.create(profile)
        return profile