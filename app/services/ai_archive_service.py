# ✅ app/services/ai_archive_service.py
# 
# ИНСТРУКЦИЯ: СОЗДАЙТЕ НОВЫЙ ФАЙЛ

import os
from typing import Optional
from datetime import datetime

from app.database.database import get_session
from app.models import Consultation, ConsultationMessage


class AIArchiveService:
    """
    Сервис для архивирования консультаций в канал
    
    Пока простая заглушка - в будущем можно добавить:
    - Генерацию красивого отчета с помощью AI
    - Отправку в специальный архивный канал
    - Поиск по архиву
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.archive_channel_id = os.getenv("ARCHIVE_CHANNEL_ID")
    
    async def archive_consultation_to_channel(self, consultation_id: int) -> Optional[str]:
        """
        Архивирует консультацию в канал
        Возвращает ID архива или None при ошибке
        """
        
        try:
            # Получаем данные консультации
            async for session in get_session():
                consultation = await session.get(Consultation, consultation_id)
                if not consultation:
                    return None
                
                await session.refresh(consultation, ['client', 'florist'])
                
                # Получаем сообщения
                from sqlalchemy import select
                messages_result = await session.execute(
                    select(ConsultationMessage)
                    .where(ConsultationMessage.consultation_id == consultation_id)
                    .order_by(ConsultationMessage.created_at)
                )
                messages = messages_result.scalars().all()
                
                # Формируем архивный отчет
                archive_text = self._generate_archive_text(consultation, messages)
                
                # Если есть канал - отправляем туда
                if self.archive_channel_id:
                    try:
                        archive_message = await self.bot.send_message(
                            chat_id=self.archive_channel_id,
                            text=archive_text,
                            parse_mode="HTML"
                        )
                        
                        # Возвращаем ID сообщения как ID архива
                        return f"archive_{archive_message.message_id}"
                        
                    except Exception as e:
                        print(f"Error sending to archive channel: {e}")
                        return None
                else:
                    # Если канала нет, просто логируем
                    print(f"📋 Archive for consultation {consultation_id}:")
                    print(archive_text)
                    return f"local_archive_{consultation_id}_{int(datetime.utcnow().timestamp())}"
                    
        except Exception as e:
            print(f"Archive error: {e}")
            return None
    
    async def restore_consultation_from_archive(self, chat_id: int, archive_id: str) -> bool:
        """
        Восстанавливает консультацию из архива в чат
        Возвращает True если успешно
        """
        
        try:
            # Пока простая заглушка
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"📖 Восстановление архива {archive_id}\n\n"
                     f"🔧 Функция в разработке. Скоро здесь будет полная история консультации.",
                parse_mode="HTML"
            )
            return True
            
        except Exception as e:
            print(f"Restore error: {e}")
            return False
    
    def _generate_archive_text(self, consultation, messages) -> str:
        """Генерирует текст архива консультации"""
        
        # Базовая информация
        start_time = consultation.started_at.strftime("%d.%m.%Y %H:%M")
        end_time = consultation.completed_at.strftime("%d.%m.%Y %H:%M") if consultation.completed_at else "Не завершена"
        
        client_name = consultation.client.first_name or "Клиент"
        florist_name = consultation.florist.first_name or "Флорист"
        
        # Подсчет сообщений
        client_messages = sum(1 for msg in messages if msg.sender_id == consultation.client_id)
        florist_messages = sum(1 for msg in messages if msg.sender_id == consultation.florist_id)
        
        archive_text = f"""
📋 <b>Архив консультации #{consultation.id}</b>

👤 <b>Клиент:</b> {client_name}
🌸 <b>Флорист:</b> {florist_name}

⏰ <b>Начало:</b> {start_time}
🏁 <b>Окончание:</b> {end_time}
📊 <b>Статус:</b> {consultation.status.value}

💬 <b>Статистика сообщений:</b>
• От клиента: {client_messages}
• От флориста: {florist_messages}
• Всего: {len(messages)}

📝 <b>Краткое содержание:</b>
{"Консультация прошла успешно" if consultation.status.value == "completed" else "Консультация завершена досрочно"}

---
💡 Для полного восстановления истории используйте команду /restore_{consultation.id}
        """.strip()
        
        return archive_text