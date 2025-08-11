from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import ConsultationRepository, FloristRepository
from app.models import Consultation, ConsultationMessage, ConsultationStatusEnum
from app.exceptions import ValidationError, UserNotFoundError

class ConsultationService:
    """Сервис для работы с консультациями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.consultation_repo = ConsultationRepository(session)
        self.florist_repo = FloristRepository(session)
    
    async def start_consultation(self, client_id: int, florist_id: int) -> Consultation:
        """Начать консультацию между клиентом и флористом"""
        
        # Проверяем что у клиента нет активной консультации
        active_consultation = await self.consultation_repo.get_active_consultation(client_id)
        if active_consultation:
            raise ValidationError("У вас уже есть активная консультация")
        
        # Проверяем что флорист не занят
        florist_active = await self.consultation_repo.get_active_consultation(florist_id)
        if florist_active:
            raise ValidationError("Флорист сейчас занят с другим клиентом")
        
        # Создаем консультацию
        consultation = await self.consultation_repo.create_consultation(client_id, florist_id)
        return consultation
    
    async def get_active_consultation(self, user_id: int) -> Optional[Consultation]:
        """Получить активную консультацию пользователя"""
        return await self.consultation_repo.get_active_consultation(user_id)
    
    async def send_message(self, consultation_id: int, sender_id: int, 
                          message_text: str = None, photo_file_id: str = None) -> ConsultationMessage:
        """Отправить сообщение в консультации"""
        
        # Проверяем что консультация активна
        consultation = await self.consultation_repo.get(consultation_id)
        if not consultation or consultation.status != ConsultationStatusEnum.active:
            raise ValidationError("Консультация не активна")
        
        # Проверяем что отправитель - участник консультации
        if sender_id not in [consultation.client_id, consultation.florist_id]:
            raise ValidationError("Вы не участник этой консультации")
        
        # Добавляем сообщение
        message = await self.consultation_repo.add_message(
            consultation_id, sender_id, message_text, photo_file_id
        )
        
        # Обновляем активность флориста если он отправитель
        if sender_id == consultation.florist_id:
            await self.florist_repo.update_last_seen(sender_id)
        
        return message
    
    async def complete_consultation(self, consultation_id: int, user_id: int) -> Optional[Consultation]:
        """Завершить консультацию"""
        
        # Получаем консультацию
        consultation = await self.consultation_repo.get(consultation_id)
        if not consultation:
            raise ValidationError("Консультация не найдена")
        
        # Определяем кто завершает
        if user_id == consultation.client_id:
            completed_by = "client"
        elif user_id == consultation.florist_id:
            completed_by = "florist"
        else:
            raise ValidationError("Вы не участник этой консультации")
        
        # Завершаем консультацию
        return await self.consultation_repo.complete_consultation(consultation_id, completed_by)
    
    async def rate_florist(self, consultation_id: int, client_id: int, rating: int) -> None:
        """Поставить оценку флористу"""
        
        if not (1 <= rating <= 5):
            raise ValidationError("Рейтинг должен быть от 1 до 5")
        
        # Получаем консультацию
        consultation = await self.consultation_repo.get(consultation_id)
        if not consultation:
            raise ValidationError("Консультация не найдена")
        
        if consultation.client_id != client_id:
            raise ValidationError("Только клиент может оценить флориста")
        
        if consultation.status == ConsultationStatusEnum.active:
            raise ValidationError("Нельзя оценить во время активной консультации")
        
        # Добавляем отзыв
        await self.consultation_repo.add_review(
            consultation_id, client_id, consultation.florist_id, rating
        )
        
        # Пересчитываем рейтинг флориста
        await self.florist_repo.update_rating(consultation.florist_id)
    
    async def get_consultation_with_participants(self, consultation_id: int) -> Optional[dict]:
        """Получить консультацию с данными участников"""
        consultation = await self.consultation_repo.get(consultation_id)
        if not consultation:
            return None
        
        # Загружаем связанные данные
        await self.session.refresh(consultation, ['client', 'florist'])
        
        return {
            'consultation': consultation,
            'client': consultation.client,
            'florist': consultation.florist
        }