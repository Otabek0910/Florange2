# app/services/consultation_buffer.py

import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models import ConsultationBuffer

class ConsultationBufferService:
    """Сервис для буферизации сообщений консультаций в PostgreSQL"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add_message(self, consultation_id: int, sender_id: int, 
                         message_text: str = None, photo_file_id: str = None) -> None:
        """Добавить сообщение в буфер"""
        
        buffer_message = ConsultationBuffer(
            consultation_id=consultation_id,
            sender_id=sender_id,
            message_text=message_text,
            photo_file_id=photo_file_id
        )
        
        self.session.add(buffer_message)
        await self.session.flush()
        
        print(f"✅ Message buffered in PostgreSQL for consultation {consultation_id}")
    
    async def get_messages(self, consultation_id: int) -> List[Dict]:
        """Получить все сообщения из буфера"""
        
        result = await self.session.execute(
            select(ConsultationBuffer)
            .where(ConsultationBuffer.consultation_id == consultation_id)
            .order_by(ConsultationBuffer.created_at)
        )
        
        buffer_messages = result.scalars().all()
        
        # Преобразуем в словари
        messages = []
        for msg in buffer_messages:
            messages.append({
                'sender_id': msg.sender_id,
                'message_text': msg.message_text,
                'photo_file_id': msg.photo_file_id,
                'timestamp': msg.created_at.isoformat()
            })
        
        print(f"📥 Retrieved {len(messages)} messages from PostgreSQL buffer")
        return messages
    
    async def clear_buffer(self, consultation_id: int) -> None:
        """Очистить буфер для конкретной консультации"""
        
        await self.session.execute(
            delete(ConsultationBuffer)
            .where(ConsultationBuffer.consultation_id == consultation_id)
        )
        
        print(f"🧹 PostgreSQL buffer cleared for consultation {consultation_id}")
    
    async def cleanup_old_buffers(self, hours: int = 24) -> int:
        """Очистить старые буферы (старше N часов)"""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.session.execute(
            delete(ConsultationBuffer)
            .where(ConsultationBuffer.created_at < cutoff_time)
        )
        
        deleted_count = result.rowcount
        print(f"🧹 Cleaned {deleted_count} old buffer messages")
        return deleted_count
    
    async def get_buffer_size(self, consultation_id: int) -> int:
        """Получить количество сообщений в буфере"""
        
        result = await self.session.execute(
            select(ConsultationBuffer.id)
            .where(ConsultationBuffer.consultation_id == consultation_id)
        )
        
        return len(result.scalars().all())