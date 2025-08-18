# 🆕 app/middleware/state_validation.py
# 
# ИНСТРУКЦИЯ: ПОЛНОСТЬЮ ЗАМЕНИТЕ содержимое файла

from typing import Callable, Dict, Any, Awaitable
from datetime import datetime

from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.database.database import get_session
from app.models import Consultation, ConsultationStatusEnum
from app.handlers.consultation import ConsultationStates


class StateValidationMiddleware(BaseMiddleware):
    """
    Middleware для проверки валидности FSM состояний консультаций
    
    Проверяет:
    - Существует ли консультация в БД
    - Не истекла ли консультация  
    - Соответствует ли статус консультации состоянию FSM
    - Автоматически очищает невалидные состояния
    """
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        
        # ✅ ИСПРАВЛЕНИЕ: получаем объект сообщения правильно
        message_obj = None
        user_id = None
        
        if hasattr(event, 'message') and event.message:
            message_obj = event.message
            user_id = event.message.from_user.id if event.message.from_user else None
        elif hasattr(event, 'callback_query') and event.callback_query:
            message_obj = event.callback_query.message
            user_id = event.callback_query.from_user.id if event.callback_query.from_user else None
        
        # Если нет пользователя, пропускаем проверку
        if not user_id or not message_obj:
            return await handler(event, data)
            
        state: FSMContext = data.get('state')
        if not state:
            return await handler(event, data)
            
        # Получаем текущее состояние
        try:
            current_state = await state.get_state()
            if not current_state:
                return await handler(event, data)
        except Exception:
            # Если ошибка получения состояния, пропускаем
            return await handler(event, data)
            
        # Проверяем только состояния консультаций
        consultation_states = [
            ConsultationStates.WAITING_RESPONSE.state,
            ConsultationStates.CHATTING.state,
            ConsultationStates.RATING.state
        ]
        
        if current_state not in consultation_states:
            return await handler(event, data)
            
        # Получаем данные состояния
        try:
            state_data = await state.get_data()
            consultation_id = state_data.get('consultation_id')
            
            if not consultation_id:
                # Нет ID консультации - очищаем состояние
                await state.clear()
                return await handler(event, data)
        except Exception:
            # Ошибка получения данных состояния
            await state.clear()
            return await handler(event, data)
            
        # Проверяем консультацию в БД
        try:
            async for session in get_session():
                consultation = await session.get(Consultation, consultation_id)
                
                if not consultation:
                    # Консультация не найдена - очищаем состояние
                    await state.clear()
                    
                    # Уведомляем только если это обычное сообщение
                    if hasattr(event, 'message') and isinstance(event.message, Message):
                        try:
                            await event.message.answer(
                                "❌ Консультация не найдена. Состояние сброшено.",
                                reply_markup=None
                            )
                        except Exception:
                            pass  # Игнорируем ошибки отправки
                    
                    return await handler(event, data)
                
                # Проверяем соответствие статуса и состояния FSM
                is_state_valid = await self._validate_state_consistency(
                    current_state, consultation, state, event
                )
                
                if not is_state_valid:
                    return  # Состояние было исправлено, прерываем обработку
                    
                # Проверяем таймаут для WAITING_RESPONSE
                if (current_state == ConsultationStates.WAITING_RESPONSE.state and 
                    consultation.status == ConsultationStatusEnum.pending):
                    
                    if consultation.expires_at and consultation.expires_at < datetime.utcnow():
                        # Истекла - обновляем в БД и очищаем состояние
                        consultation.status = ConsultationStatusEnum.expired
                        await session.commit()
                        
                        await state.clear()
                        
                        # Уведомляем только если это обычное сообщение
                        if hasattr(event, 'message') and isinstance(event.message, Message):
                            try:
                                await event.message.answer(
                                    "⏰ Время ожидания консультации истекло (15 минут).\n"
                                    "Попробуйте выбрать другого флориста.",
                                    reply_markup=None
                                )
                            except Exception:
                                pass  # Игнорируем ошибки отправки
                        
                        return  # Не продолжаем обработку
                        
        except Exception as e:
            # Ошибка работы с БД - логируем и продолжаем
            print(f"StateValidation DB error: {e}")
            return await handler(event, data)
        
        # Всё валидно - продолжаем обработку
        return await handler(event, data)
    
    async def _validate_state_consistency(
        self, 
        current_state: str, 
        consultation: Consultation, 
        state: FSMContext,
        event
    ) -> bool:
        """
        Проверяет соответствие FSM состояния и статуса консультации в БД
        Возвращает True если состояние валидно, False если было исправлено
        """
        
        # Маппинг состояний FSM к статусам консультаций
        expected_statuses = {
            ConsultationStates.WAITING_RESPONSE.state: [ConsultationStatusEnum.pending],
            ConsultationStates.CHATTING.state: [ConsultationStatusEnum.active],
            ConsultationStates.RATING.state: [ConsultationStatusEnum.completed]
        }
        
        expected = expected_statuses.get(current_state, [])
        
        if consultation.status not in expected:
            # Несоответствие - исправляем состояние
            
            try:
                if consultation.status == ConsultationStatusEnum.pending:
                    # Консультация pending, но состояние не WAITING_RESPONSE
                    await state.set_state(ConsultationStates.WAITING_RESPONSE)
                    await state.update_data(consultation_id=consultation.id)
                    
                elif consultation.status == ConsultationStatusEnum.active:
                    # Консультация активна, но состояние не CHATTING  
                    await state.set_state(ConsultationStates.CHATTING)
                    await state.update_data(consultation_id=consultation.id)
                    
                elif consultation.status in [ConsultationStatusEnum.completed, ConsultationStatusEnum.expired]:
                    # Консультация завершена - очищаем состояние
                    await state.clear()
                    
                    # Уведомляем только если это обычное сообщение
                    if hasattr(event, 'message') and isinstance(event.message, Message):
                        try:
                            status_text = "завершена" if consultation.status == ConsultationStatusEnum.completed else "истекла"
                            await event.message.answer(
                                f"ℹ️ Консультация {status_text}. Состояние обновлено.",
                                reply_markup=None
                            )
                        except Exception:
                            pass  # Игнорируем ошибки отправки
                            
            except Exception as e:
                print(f"State sync error: {e}")
                # При ошибке просто очищаем состояние
                try:
                    await state.clear()
                except Exception:
                    pass
            
            return False  # Состояние было исправлено
            
        return True  # Состояние валидно


class ConsultationCleanupMiddleware(BaseMiddleware):
    """
    Middleware для периодической очистки истёкших консультаций
    Выполняется раз в N сообщений для снижения нагрузки
    """
    
    def __init__(self, cleanup_frequency: int = 100):
        self.cleanup_frequency = cleanup_frequency
        self.message_count = 0
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        
        # Увеличиваем счётчик сообщений
        self.message_count += 1
        
        # Периодически запускаем очистку
        if self.message_count % self.cleanup_frequency == 0:
            try:
                async for session in get_session():
                    # Используем SQL функцию из миграции
                    result = await session.execute("SELECT cleanup_expired_consultations()")
                    count = result.scalar()
                    
                    if count > 0:
                        print(f"🧹 Cleaned up {count} expired consultations")
                        
            except Exception as e:
                print(f"Cleanup error: {e}")
        
        # Продолжаем обработку
        return await handler(event, data)