# ✅ app/services/florist_service.py
# 
# ИНСТРУКЦИЯ: СОЗДАЙТЕ НОВЫЙ ФАЙЛ

from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, RoleEnum, FloristProfile, Consultation, ConsultationStatusEnum


class FloristService:
    """Сервис для работы с флористами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_available_florists(self) -> List[Dict[str, Any]]:
        """Получить список доступных флористов с их статусами"""
        
        # Получаем всех флористов с профилями
        result = await self.session.execute(
            select(User, FloristProfile)
            .join(FloristProfile, User.id == FloristProfile.user_id)
            .where(
                and_(
                    User.role.in_([RoleEnum.florist, RoleEnum.owner]),
                    FloristProfile.is_active == True
                )
            )
            .order_by(FloristProfile.rating.desc())
        )
        
        florists_data = result.all()
        available_florists = []
        
        for user, profile in florists_data:
            # Проверяем есть ли активная консультация
            active_consultation = await self.session.execute(
                select(Consultation).where(
                    and_(
                        Consultation.florist_id == user.id,
                        Consultation.status == ConsultationStatusEnum.active
                    )
                )
            )
            
            is_busy = active_consultation.scalars().first() is not None
            
            # Определяем онлайн статус (последняя активность < 5 минут)
            is_online = False
            if profile.last_seen:
                is_online = (datetime.utcnow() - profile.last_seen) < timedelta(minutes=5)
            
            # Формируем статус
            if is_busy:
                status_text = "Занят консультацией"
                is_available = False
            elif is_online:
                status_text = "Онлайн"
                is_available = True
            else:
                status_text = "Офлайн"
                is_available = True  # Офлайн флористы тоже доступны для записи
            
            # Формируем рейтинг
            if profile.rating > 0 and profile.reviews_count > 0:
                rating_text = f"⭐{profile.rating:.1f} ({profile.reviews_count})"
            else:
                rating_text = "⭐Новый"
            
            florist_data = {
                'user': user,
                'profile': profile,
                'is_online': is_online,
                'is_busy': is_busy,
                'is_available': is_available,
                'status_text': status_text,
                'rating_text': rating_text
            }
            
            available_florists.append(florist_data)
        
        return available_florists
    
    async def update_florist_last_seen(self, florist_id: int):
        """Обновить время последней активности флориста"""
        profile = await self.session.execute(
            select(FloristProfile).where(FloristProfile.user_id == florist_id)
        )
        profile_obj = profile.scalar_one_or_none()
        
        if profile_obj:
            profile_obj.last_seen = datetime.utcnow()
    
    async def get_florist_profile(self, florist_id: int) -> FloristProfile:
        """Получить профиль флориста"""
        result = await self.session.execute(
            select(FloristProfile).where(FloristProfile.user_id == florist_id)
        )
        return result.scalar_one_or_none()
    
    async def create_florist_profile(self, user_id: int, **profile_data) -> FloristProfile:
        """Создать профиль флориста"""
        profile = FloristProfile(
            user_id=user_id,
            bio=profile_data.get('bio', ''),
            specialization=profile_data.get('specialization', ''),
            is_active=True,
            last_seen=datetime.utcnow(),
            rating=0.0,
            reviews_count=0
        )
        
        self.session.add(profile)
        return profile
    
    async def update_activity(self, user_id: int):
        """Обновить время последней активности флориста"""
        try:
            profile = await self.get_or_create_profile(user_id)
            profile.last_seen = datetime.utcnow()
            # session.commit() будет вызван в middleware
        except Exception as e:
            # Логируем, но не падаем
            print(f"Failed to update florist activity for user {user_id}: {e}")