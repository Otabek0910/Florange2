from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from .base import BaseRepository
from app.models import (
    Consultation, 
    ConsultationMessage, 
    FloristReview,
    ConsultationStatusEnum
)

class ConsultationRepository(BaseRepository[Consultation]):
    """Репозиторий для работы с консультациями"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Consultation)
    
    async def get_active_consultation(self, user_id: int) -> Optional[Consultation]:
        """Получить активную консультацию для пользователя (клиента или флориста)"""
        result = await self.session.execute(
            select(Consultation)
            .where(
                and_(
                    Consultation.status == ConsultationStatusEnum.active,
                    (
                        (Consultation.client_id == user_id) |
                        (Consultation.florist_id == user_id)
                    )
                )
            )
        )
        return result.scalars().first()
    
    async def get_user_consultations(self, user_id: int, limit: int = 10) -> List[Consultation]:
        """Получить консультации пользователя"""
        result = await self.session.execute(
            select(Consultation)
            .where(
                (Consultation.client_id == user_id) |
                (Consultation.florist_id == user_id)
            )
            .order_by(Consultation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create_consultation(self, client_id: int, florist_id: int) -> Consultation:
        """Создать новую консультацию"""
        consultation = Consultation(
            client_id=client_id,
            florist_id=florist_id,
            status=ConsultationStatusEnum.active
        )
        return await self.create(consultation)
    
    async def complete_consultation(self, consultation_id: int, completed_by: str) -> Optional[Consultation]:
        """Завершить консультацию"""
        consultation = await self.get(consultation_id)
        if consultation and consultation.status == ConsultationStatusEnum.active:
            if completed_by == "client":
                consultation.status = ConsultationStatusEnum.completed_by_client
            elif completed_by == "florist":
                consultation.status = ConsultationStatusEnum.completed_by_florist
            
            consultation.completed_at = datetime.utcnow()
            await self.session.flush()
            return consultation
        return None
    
    async def add_message(self, consultation_id: int, sender_id: int, 
                         message_text: str = None, photo_file_id: str = None) -> ConsultationMessage:
        """Добавить сообщение в консультацию"""
        message = ConsultationMessage(
            consultation_id=consultation_id,
            sender_id=sender_id,
            message_text=message_text,
            photo_file_id=photo_file_id
        )
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message
    
    async def add_review(self, consultation_id: int, client_id: int, 
                        florist_id: int, rating: int) -> FloristReview:
        """Добавить отзыв о флористе"""
        review = FloristReview(
            consultation_id=consultation_id,
            client_id=client_id,
            florist_id=florist_id,
            rating=rating
        )
        self.session.add(review)
        await self.session.flush()
        await self.session.refresh(review)
        return review
    
    async def get_messages(self, consultation_id: int) -> List[ConsultationMessage]:
        """Получить сообщения консультации"""
        result = await self.session.execute(
            select(ConsultationMessage)
            .where(ConsultationMessage.consultation_id == consultation_id)
            .order_by(ConsultationMessage.created_at)
        )
        return result.scalars().all()

    async def get_active_or_pending_consultation(self, user_id: int) -> Optional[Consultation]:
        """Получить активную ИЛИ pending консультацию для пользователя"""
        result = await self.session.execute(
            select(Consultation)
            .where(
                and_(
                    Consultation.status.in_([
                        ConsultationStatusEnum.active, 
                        ConsultationStatusEnum.pending
                    ]),
                    (
                        (Consultation.client_id == user_id) |
                        (Consultation.florist_id == user_id)
                    )
                )
            )
        )
        return result.scalars().first()