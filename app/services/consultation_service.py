# ✅ app/services/consultation_service.py
# 
# ИНСТРУКЦИЯ: СОЗДАЙТЕ НОВЫЙ ФАЙЛ или полностью замените содержимое

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Consultation, ConsultationStatusEnum, User, RoleEnum,
    FloristProfile, ConsultationMessage, ConsultationBuffer
)
from app.exceptions import ValidationError, UserNotFoundError


def generate_request_key(client_id: int, florist_id: int) -> str:
    """Генерирует ключ идемпотентности для запроса консультации"""
    timestamp = int(datetime.utcnow().timestamp() // 60)  # Округляем до минут
    return f"consult_{client_id}_{florist_id}_{timestamp}"


class ConsultationService:
    """Сервис для работы с консультациями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_active_consultation(self, user_id: int) -> Optional[Consultation]:
        """Получить активную консультацию пользователя"""
        result = await self.session.execute(
            select(Consultation).where(
                and_(
                    ((Consultation.client_id == user_id) | (Consultation.florist_id == user_id)),
                    Consultation.status.in_([ConsultationStatusEnum.pending, ConsultationStatusEnum.active])
                )
            )
        )
        return result.scalars().first()
    
    async def request_consultation(self, client_id: int, florist_id: int) -> Consultation:
        """Создать запрос на консультацию (старый метод для совместимости)"""
        request_key = generate_request_key(client_id, florist_id)
        return await self.request_consultation_idempotent(client_id, florist_id, request_key)
    
    async def request_consultation_idempotent(
        self, 
        client_id: int, 
        florist_id: int, 
        request_key: str
    ) -> Consultation:
        """✅ ИСПРАВЛЕННЫЙ метод создания консультации с идемпотентностью"""
        
        # Проверяем существующую консультацию по ключу
        existing = await self.session.execute(
            select(Consultation).where(
                and_(
                    Consultation.request_key == request_key,
                    Consultation.status.in_([ConsultationStatusEnum.pending, ConsultationStatusEnum.active])
                )
            )
        )
        
        existing_consultation = existing.scalars().first()
        if existing_consultation:
            return existing_consultation
        
        # Проверяем что клиент не имеет активных консультаций
        active_client_consultation = await self.session.execute(
            select(Consultation).where(
                and_(
                    Consultation.client_id == client_id,
                    Consultation.status.in_([ConsultationStatusEnum.pending, ConsultationStatusEnum.active])
                )
            )
        )
        
        if active_client_consultation.scalars().first():
            raise ValidationError("У вас уже есть активная консультация")
        
        # Проверяем что флорист существует и доступен
        florist = await self.session.get(User, florist_id)
        if not florist or florist.role not in [RoleEnum.florist, RoleEnum.owner]:
            raise ValidationError("Флорист не найден или недоступен")
        
        # Создаем новую консультацию
        consultation = Consultation(
            client_id=client_id,
            florist_id=florist_id,
            status=ConsultationStatusEnum.pending,
            request_key=request_key,
            expires_at=datetime.utcnow() + timedelta(minutes=15),  # 15 минут на ответ
            started_at=datetime.utcnow()
        )
        
        self.session.add(consultation)
        await self.session.flush()  # Получаем ID
        
        return consultation
    
    async def accept_consultation(self, consultation_id: int, florist_id: int) -> Consultation:
        """Принять консультацию флористом"""
        consultation = await self.session.get(Consultation, consultation_id)
        
        if not consultation:
            raise ValidationError("Консультация не найдена")
        
        if consultation.florist_id != florist_id:
            raise ValidationError("Вы не назначены на эту консультацию")
        
        if consultation.status != ConsultationStatusEnum.pending:
            raise ValidationError("Консультация уже обработана")
        
        # Проверяем что флорист не занят другой консультацией
        active_florist_consultation = await self.session.execute(
            select(Consultation).where(
                and_(
                    Consultation.florist_id == florist_id,
                    Consultation.status == ConsultationStatusEnum.active,
                    Consultation.id != consultation_id
                )
            )
        )
        
        if active_florist_consultation.scalars().first():
            raise ValidationError("У вас уже есть активная консультация")
        
        # Активируем консультацию
        consultation.status = ConsultationStatusEnum.active
        consultation.started_at = datetime.utcnow()
        consultation.expires_at = None  # Убираем ограничение по времени
        
        return consultation
    
    async def decline_consultation(self, consultation_id: int, florist_id: int) -> Consultation:
        """Отклонить консультацию флористом"""
        consultation = await self.session.get(Consultation, consultation_id)
        
        if not consultation:
            raise ValidationError("Консультация не найдена")
        
        if consultation.florist_id != florist_id:
            raise ValidationError("Вы не назначены на эту консультацию")
        
        if consultation.status != ConsultationStatusEnum.pending:
            raise ValidationError("Консультация уже обработана")
        
        # Отклоняем консультацию
        consultation.status = ConsultationStatusEnum.declined
        consultation.completed_at = datetime.utcnow()
        
        return consultation
    
    async def complete_consultation(self, consultation_id: int, user_id: int) -> Consultation:
        """Завершить консультацию"""
        consultation = await self.session.get(Consultation, consultation_id)
        
        if not consultation:
            raise ValidationError("Консультация не найдена")
        
        if user_id not in [consultation.client_id, consultation.florist_id]:
            raise ValidationError("Вы не участвуете в этой консультации")
        
        if consultation.status != ConsultationStatusEnum.active:
            raise ValidationError("Консультация не активна")
        
        # Завершаем консультацию
        consultation.status = ConsultationStatusEnum.completed
        consultation.completed_at = datetime.utcnow()
        
        return consultation
    
    async def get_consultation_messages(self, consultation_id: int) -> List[ConsultationMessage]:
        """Получить сообщения консультации"""
        result = await self.session.execute(
            select(ConsultationMessage)
            .where(ConsultationMessage.consultation_id == consultation_id)
            .order_by(ConsultationMessage.created_at)
        )
        return result.scalars().all()
    
    async def add_message(
        self, 
        consultation_id: int, 
        sender_id: int, 
        message_text: str = "", 
        photo_file_id: str = None
    ) -> ConsultationMessage:
        """Добавить сообщение в консультацию"""
        
        # Проверяем что консультация активна
        consultation = await self.session.get(Consultation, consultation_id)
        if not consultation or consultation.status != ConsultationStatusEnum.active:
            raise ValidationError("Консультация не активна")
        
        # Проверяем права отправителя
        if sender_id not in [consultation.client_id, consultation.florist_id]:
            raise ValidationError("Вы не участвуете в этой консультации")
        
        message = ConsultationMessage(
            consultation_id=consultation_id,
            sender_id=sender_id,
            message_text=message_text,
            photo_file_id=photo_file_id,
            sent_at=datetime.utcnow()
        )
        
        self.session.add(message)
        return message
    
    async def cleanup_expired_consultations(self) -> int:
        """Очистить истёкшие консультации"""
        result = await self.session.execute(
            select(Consultation).where(
                and_(
                    Consultation.status == ConsultationStatusEnum.pending,
                    Consultation.expires_at < datetime.utcnow()
                )
            )
        )
        
        expired_consultations = result.scalars().all()
        count = len(expired_consultations)
        
        for consultation in expired_consultations:
            consultation.status = ConsultationStatusEnum.expired
            consultation.completed_at = datetime.utcnow()
        
        return count