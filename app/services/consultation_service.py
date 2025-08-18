# 🔧 app/services/consultation_service.py
# 
# ИНСТРУКЦИЯ: Найдите этот файл и ЗАМЕНИТЕ весь класс ConsultationService на код ниже

import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.orm import selectinload

from app.repositories import ConsultationRepository, FloristRepository
from app.models import Consultation, ConsultationMessage, ConsultationStatusEnum, ConsultationBuffer
from app.exceptions import ValidationError, UserNotFoundError


def generate_request_key(client_id: int, florist_id: int) -> str:
    """Генерация ключа идемпотентности"""
    # Округляем до минуты для предотвращения спама
    timestamp = int(datetime.utcnow().timestamp() // 60)
    return f"consult_{client_id}_{florist_id}_{timestamp}"


class NotificationCircuitBreaker:
    """Circuit Breaker для внешних уведомлений"""
    
    def __init__(self, failure_threshold=3, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time < self.timeout:
                raise Exception("Circuit breaker is OPEN")
            else:
                self.state = "HALF_OPEN"
        
        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise e


class ConsultationService:
    """Сервис для работы с консультациями (исправленная версия)"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.consultation_repo = ConsultationRepository(session)
        self.florist_repo = FloristRepository(session)
        self.circuit_breaker = NotificationCircuitBreaker()

    async def request_consultation_idempotent(self, client_id: int, florist_id: int, request_key: str) -> Consultation:
        """🆕 Идемпотентный запрос консультации с защитой от гонок"""
        
        # ✅ ИСПРАВЛЕНИЕ: НЕ создаём новую транзакцию, используем существующую
        
        # 1. Проверяем существующий запрос (идемпотентность)
        existing_query = select(Consultation).where(
            or_(
                Consultation.request_key == request_key,
                and_(
                    Consultation.client_id == client_id,
                    Consultation.status.in_(['active', 'pending'])
                )
            )
        ).with_for_update(skip_locked=True)
        
        result = await self.session.execute(existing_query)
        existing = result.scalar_one_or_none()
        
        if existing:
            return existing  # Идемпотентный возврат
        
        # 2. Проверяем доступность флориста с блокировкой
        florist_busy_query = select(Consultation).where(
            and_(
                Consultation.florist_id == florist_id,
                Consultation.status.in_(['active', 'pending'])
            )
        ).with_for_update(skip_locked=True)
        
        florist_busy_result = await self.session.execute(florist_busy_query)
        florist_busy = florist_busy_result.scalar_one_or_none()
        
        if florist_busy:
            raise ValidationError("Флорист сейчас занят с другим клиентом")
        
        # 3. Создаём консультацию атомарно
        consultation = Consultation(
            client_id=client_id,
            florist_id=florist_id,
            status=ConsultationStatusEnum.pending,
            request_key=request_key,
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        
        self.session.add(consultation)
        await self.session.flush()  # Получаем ID
        
        return consultation

    async def accept_consultation(self, consultation_id: int, florist_id: int) -> Consultation:
        """Принятие консультации флористом"""
        
        # ✅ ИСПРАВЛЕНИЕ: НЕ создаём новую транзакцию
        
        # Блокируем консультацию для обновления
        query = select(Consultation).where(
            and_(
                Consultation.id == consultation_id,
                Consultation.florist_id == florist_id,
                Consultation.status == ConsultationStatusEnum.pending
            )
        ).with_for_update()
        
        result = await self.session.execute(query)
        consultation = result.scalar_one_or_none()
        
        if not consultation:
            raise ValidationError("Консультация не найдена или уже неактивна")
        
        # Проверяем что не истекла
        if consultation.expires_at and consultation.expires_at < datetime.utcnow():
            consultation.status = ConsultationStatusEnum.expired
            await self.session.flush()
            raise ValidationError("Консультация истекла")
        
        # Активируем консультацию
        consultation.status = ConsultationStatusEnum.active
        consultation.started_at = datetime.utcnow()
        consultation.expires_at = None  # Убираем таймаут
        
        await self.session.flush()
        
        # Доставляем буферные сообщения
        await self._deliver_buffered_messages(consultation_id)
        
        return consultation

    async def decline_consultation(self, consultation_id: int, florist_id: int) -> Consultation:
        """Отклонение консультации флористом"""
        
        # ✅ ИСПРАВЛЕНИЕ: НЕ создаём новую транзакцию
        
        query = select(Consultation).where(
            and_(
                Consultation.id == consultation_id,
                Consultation.florist_id == florist_id,
                Consultation.status == ConsultationStatusEnum.pending
            )
        ).with_for_update()
        
        result = await self.session.execute(query)
        consultation = result.scalar_one_or_none()
        
        if not consultation:
            raise ValidationError("Консультация не найдена")
        
        consultation.status = ConsultationStatusEnum.completed
        consultation.completed_at = datetime.utcnow()
        
        # Очищаем буфер
        await self._clear_buffered_messages(consultation_id)
        
        return consultation

    async def add_buffered_message(self, consultation_id: int, sender_id: int, 
                                 message_text: str = None, photo_file_id: str = None):
        """Добавление сообщения в буфер (пока флорист не ответил)"""
        
        buffer_msg = ConsultationBuffer(
            consultation_id=consultation_id,
            sender_id=sender_id,
            message_text=message_text,
            photo_file_id=photo_file_id
        )
        
        self.session.add(buffer_msg)
        await self.session.commit()

    async def _deliver_buffered_messages(self, consultation_id: int):
        """Доставка буферных сообщений с гарантиями"""
        
        # Получаем все буферные сообщения
        query = select(ConsultationBuffer).where(
            ConsultationBuffer.consultation_id == consultation_id
        ).order_by(ConsultationBuffer.created_at).with_for_update()
        
        result = await self.session.execute(query)
        buffered_messages = result.scalars().all()
        
        if not buffered_messages:
            return
        
        # Получаем консультацию с участниками
        consultation_query = select(Consultation).options(
            selectinload(Consultation.client),
            selectinload(Consultation.florist)
        ).where(Consultation.id == consultation_id)
        
        consultation_result = await self.session.execute(consultation_query)
        consultation = consultation_result.scalar_one()
        
        # Переносим сообщения в основную таблицу
        for msg in buffered_messages:
            consultation_msg = ConsultationMessage(
                consultation_id=consultation_id,
                sender_id=msg.sender_id,
                message_text=msg.message_text,
                photo_file_id=msg.photo_file_id,
                created_at=msg.created_at
            )
            self.session.add(consultation_msg)
        
        # Удаляем из буфера
        await self._clear_buffered_messages(consultation_id)

    async def _clear_buffered_messages(self, consultation_id: int):
        """Очистка буферных сообщений"""
        delete_query = delete(ConsultationBuffer).where(
            ConsultationBuffer.consultation_id == consultation_id
        )
        await self.session.execute(delete_query)

    async def complete_consultation(self, consultation_id: int, user_id: int):
        """Завершение консультации"""
        
        # ✅ ИСПРАВЛЕНИЕ: НЕ создаём новую транзакцию
        
        query = select(Consultation).where(
            and_(
                Consultation.id == consultation_id,
                or_(
                    Consultation.client_id == user_id,
                    Consultation.florist_id == user_id
                ),
                Consultation.status == ConsultationStatusEnum.active
            )
        ).with_for_update()
        
        result = await self.session.execute(query)
        consultation = result.scalar_one_or_none()
        
        if not consultation:
            raise ValidationError("Консультация не найдена или уже завершена")
        
        consultation.status = ConsultationStatusEnum.completed
        consultation.completed_at = datetime.utcnow()
        
        return consultation

    async def cleanup_expired_consultations(self) -> int:
        """Очистка истёкших консультаций"""
        
        # Используем SQL функцию из миграции
        result = await self.session.execute("SELECT cleanup_expired_consultations()")
        count = result.scalar()
        await self.session.commit()
        
        return count

    # Старые методы для обратной совместимости
    async def request_consultation(self, client_id: int, florist_id: int) -> Consultation:
        """Обёртка для старого метода"""
        request_key = generate_request_key(client_id, florist_id)
        return await self.request_consultation_idempotent(client_id, florist_id, request_key)

    async def get_active_consultation(self, user_id: int) -> Optional[Consultation]:
        """Получить активную консультацию пользователя"""
        query = select(Consultation).where(
            and_(
                or_(
                    Consultation.client_id == user_id,
                    Consultation.florist_id == user_id
                ),
                Consultation.status.in_(['active', 'pending'])
            )
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()