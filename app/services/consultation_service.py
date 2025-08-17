import asyncio
from datetime import datetime
from typing import Optional, List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import ConsultationRepository, FloristRepository
from app.models import Consultation, ConsultationMessage, ConsultationStatusEnum
from app.exceptions import ValidationError, UserNotFoundError
from app.services.consultation_buffer import ConsultationBuffer

class ConsultationService:
    """Сервис для работы с консультациями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.consultation_repo = ConsultationRepository(session)
        self.florist_repo = FloristRepository(session)
        self.buffer = ConsultationBuffer()  # 🆕

    # НОВЫЕ ФУНКЦИИ
    
    async def request_consultation(self, client_id: int, florist_id: int) -> Consultation:
        """🆕 Запросить консультацию (создает в статусе pending)"""
        
        # Проверяем что у клиента нет активных консультаций
        active_consultation = await self.consultation_repo.get_active_or_pending_consultation(client_id)
        if active_consultation:
            raise ValidationError("У вас уже есть активная консультация")
        
        # Проверяем что флорист не занят
        florist_consultation = await self.consultation_repo.get_active_consultation(florist_id)
        if florist_consultation:
            raise ValidationError("Флорист сейчас занят с другим клиентом")
        
        # Создаем консультацию в статусе pending
        consultation = Consultation(
            client_id=client_id,
            florist_id=florist_id,
            status=ConsultationStatusEnum.pending  # 🆕 Не active!
        )
        consultation = await self.consultation_repo.create(consultation)
        
        # Запускаем таймер на 10 минут
        asyncio.create_task(self._timeout_consultation(consultation.id))
        
        return consultation
    
    async def accept_consultation(self, consultation_id: int, florist_id: int) -> Consultation:
        """🆕 Флорист принимает консультацию"""
        
        consultation = await self.consultation_repo.get(consultation_id)
        if not consultation:
            raise ValidationError("Консультация не найдена")
        
        if consultation.florist_id != florist_id:
            raise ValidationError("Это не ваша консультация")
        
        if consultation.status != ConsultationStatusEnum.pending:
            raise ValidationError("Консультация уже не ожидает ответа")
        
        # Меняем статус на active
        consultation.status = ConsultationStatusEnum.active
        await self.session.flush()
        
        return consultation
    
    async def add_buffered_message(self, consultation_id: int, sender_id: int, 
                                  message_text: str = None, photo_file_id: str = None) -> None:
        """🆕 Добавить сообщение в буфер (для pending консультаций)"""
        
        message_data = {
            'sender_id': sender_id,
            'message_text': message_text,
            'photo_file_id': photo_file_id,
            'consultation_id': consultation_id
        }
        
        await self.buffer.add_message(consultation_id, message_data)
    
    async def get_buffered_messages(self, consultation_id: int) -> List[Dict]:
        """🆕 Получить буферизованные сообщения"""
        return await self.buffer.get_messages(consultation_id)
    
    async def flush_buffer_to_active(self, consultation_id: int) -> List[Dict]:
        """🆕 Перенести все сообщения из буфера в активную консультацию"""
        
        # Получаем сообщения из буфера
        messages = await self.buffer.get_messages(consultation_id)
        
        # Очищаем буфер
        await self.buffer.clear_buffer(consultation_id)
        
        return messages
    
    async def _timeout_consultation(self, consultation_id: int) -> None:
        """🆕 Таймаут консультации через 10 минут"""
        await asyncio.sleep(600)  # 10 минут
        
        try:
            consultation = await self.consultation_repo.get(consultation_id)
            if consultation and consultation.status == ConsultationStatusEnum.pending:
                consultation.status = ConsultationStatusEnum.timeout_no_response
                consultation.completed_at = datetime.utcnow()
                await self.session.commit()
                
                # Уведомляем клиента
                await self._notify_consultation_timeout(consultation)
                
        except Exception as e:
            print(f"Timeout error: {e}")
    
    async def _notify_consultation_timeout(self, consultation) -> None:
        """🆕 Уведомить клиента о таймауте"""
        # Тут будет логика уведомления через бота
        pass
        
    # СТАРЫЕ ФУНКЦИИ

    async def start_consultation(self, client_id: int, florist_id: int) -> Consultation:
        """ОБНОВЛЕНО: Теперь создает pending консультацию"""
        return await self.request_consultation(client_id, florist_id)
    
    async def get_active_consultation(self, user_id: int) -> Optional[Consultation]:
        """ОБНОВЛЕНО: Получить активную ИЛИ pending консультацию пользователя"""
        return await self.consultation_repo.get_active_or_pending_consultation(user_id)
    
    async def send_message(self, consultation_id: int, sender_id: int, 
                          message_text: str = None, photo_file_id: str = None) -> ConsultationMessage:
        """ОБНОВЛЕНО: Отправить сообщение в консультацию или буфер"""
        
        # Получаем консультацию
        consultation = await self.consultation_repo.get(consultation_id)
        if not consultation:
            raise ValidationError("Консультация не найдена")
        
        # Проверяем что отправитель - участник консультации
        if sender_id not in [consultation.client_id, consultation.florist_id]:
            raise ValidationError("Вы не участник этой консультации")
        
        # Если консультация pending - добавляем в буфер
        if consultation.status == ConsultationStatusEnum.pending:
            await self.add_buffered_message(consultation_id, sender_id, message_text, photo_file_id)
            return None  # Сообщение в буфере, не в БД
        
        # Если консультация active - сохраняем в БД как обычно
        elif consultation.status == ConsultationStatusEnum.active:
            message = await self.consultation_repo.add_message(
                consultation_id, sender_id, message_text, photo_file_id
            )
            
            # Обновляем активность флориста если он отправитель
            if sender_id == consultation.florist_id:
                await self.florist_repo.update_last_seen(sender_id)
            
            return message
        
        else:
            raise ValidationError("Консультация не активна")
    
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