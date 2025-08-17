# app/services/consultation_buffer.py

import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class ConsultationBuffer:
    # Глобальное хранилище в памяти

    _memory_storage = {}
    
    def __init__(self, redis_client=None):
        self.redis = redis_client or self._get_redis()
    
    def _get_redis(self):
        """Получить Redis клиент (fallback на память если Redis недоступен)"""
        try:
            import redis.asyncio as redis
            from app.config import settings
            return redis.Redis.from_url(settings.REDIS_URL)
        except Exception as e:
            print(f"⚠️ Redis недоступен, используем память: {e}")
            return None  # Возвращаем None, чтобы использовать память
    
    async def add_message(self, consultation_id: int, message_data: Dict) -> None:
        """Добавить сообщение в буфер"""
        key = f"consultation:{consultation_id}:buffer"
        message_data['timestamp'] = datetime.utcnow().isoformat()
        
        try:
            if self.redis:  # Реальный Redis
                await self.redis.lpush(key, json.dumps(message_data))
                await self.redis.expire(key, 900)  # TTL 15 минут
                print(f"✅ Message buffered in Redis for consultation {consultation_id}")
            else:  # Fallback память
                if key not in self._memory_storage:
                    self._memory_storage[key] = []
                self._memory_storage[key].append(message_data)
                print(f"✅ Message buffered in memory, key: {key}")
                
                # Автоочистка через 15 минут
                import asyncio
                asyncio.create_task(self._auto_cleanup(key, 900))  # 15 минут
                
        except Exception as e:
            print(f"❌ Buffer error: {e}")
    
    async def get_messages(self, consultation_id: int) -> List[Dict]:
        """Получить все сообщения из буфера"""
        key = f"consultation:{consultation_id}:buffer"
        
        try:
            if self.redis:  # Реальный Redis
                messages = await self.redis.lrange(key, 0, -1)
                result = [json.loads(msg) for msg in reversed(messages)]
                print(f"📥 Retrieved {len(result)} messages from Redis buffer")
                return result
            else:  # Fallback память
                result = self._memory_storage.get(key, [])
                print(f"📥 Retrieved {len(result)} messages from memory buffer")
                return result
        except Exception as e:
            print(f"❌ Buffer get error: {e}")
            return []
    
    async def clear_buffer(self, consultation_id: int) -> None:
        """Очистить буфер"""
        key = f"consultation:{consultation_id}:buffer"
        
        try:
            if self.redis:  # Реальный Redis
                await self.redis.delete(key)
                print(f"🧹 Redis buffer cleared for consultation {consultation_id}")
            else:  # Fallback память
                self._memory_storage.pop(key, None)
                print(f"🧹 Memory buffer cleared for consultation {consultation_id}")
        except Exception as e:
            print(f"❌ Buffer clear error: {e}")
    
    async def _auto_cleanup(self, key: str, delay: int):
        """Автоматическая очистка буфера через delay секунд"""
        await asyncio.sleep(delay)
        try:
            if key in self._memory_storage:
                del self._memory_storage[key]
                print(f"🧹 Auto-cleaned memory buffer: {key}")
        except Exception as e:
            print(f"❌ Auto-cleanup error: {e}")