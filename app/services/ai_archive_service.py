import aiohttp
import json
from typing import List, Optional
from aiogram import Bot

from app.config import settings
from app.models import Consultation, ConsultationMessage

class AIArchiveService:
    """Сервис для работы с ИИ и архивом консультаций"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def generate_consultation_theme(self, messages: List[ConsultationMessage]) -> str:
        """Генерация темы консультации через Yandex GPT"""
        try:
            # Берем первые 3-5 сообщений клиента
            client_messages = [msg.message_text for msg in messages[:5] if msg.message_text]
            if not client_messages:
                return "Консультация флориста"
            
            # Формируем промпт
            conversation = " ".join(client_messages[:3])
            prompt = f"""Создай краткую тему консультации (максимум 30 символов) на основе этих сообщений клиента флористу:
            
"{conversation}"

Примеры хороших тем:
- "Выбор роз для свадьбы"
- "Уход за орхидеями"
- "Букет на день рождения"
- "Композиция в офис"

Ответь только темой без кавычек и объяснений:"""

            # Если нет API ключа - используем простую логику
            if not settings.YANDEX_GPT_API_KEY:
                return self._generate_simple_theme(client_messages[0])
            
            # Вызов Yandex GPT API
            theme = await self._call_yandex_gpt(prompt)
            return theme[:30] if theme else self._generate_simple_theme(client_messages[0])
            
        except Exception as e:
            print(f"Error generating theme with AI: {e}")
            return self._generate_simple_theme(client_messages[0] if client_messages else "")
    
    async def _call_yandex_gpt(self, prompt: str) -> str:
        """Вызов Yandex GPT API"""
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {settings.YANDEX_GPT_API_KEY}"
        }
        
        data = {
            "modelUri": f"gpt://{settings.YANDEX_FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": 50
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["result"]["alternatives"][0]["message"]["text"].strip()
                else:
                    print(f"Yandex GPT API error: {response.status}")
                    return ""
    
    def _generate_simple_theme(self, first_message: str) -> str:
        """Простая генерация темы без ИИ"""
        if not first_message:
            return "Консультация флориста"
        
        # Убираем лишние символы и берем первые 30 символов
        clean_text = first_message.strip()[:30]
        
        # Простые правила
        if any(word in clean_text.lower() for word in ["свадьба", "свадебн"]):
            return "Свадебная консультация"
        elif any(word in clean_text.lower() for word in ["роз", "красн"]):
            return "Консультация по розам"
        elif any(word in clean_text.lower() for word in ["букет", "цвет"]):
            return "Выбор букета"
        elif any(word in clean_text.lower() for word in ["уход", "полив"]):
            return "Уход за растениями"
        else:
            return f"Консультация: {clean_text[:20]}..."
    
    async def archive_consultation(self, consultation: Consultation, messages: List[ConsultationMessage]) -> str:
        """Архивирование консультации в Telegram канал"""
        try:
            archive_id = f"ARCHIVE_{consultation.id}"
            
            # Формируем заголовок архива
            client_name = consultation.client.first_name or "Клиент"
            florist_name = consultation.florist.first_name or "Флорист"
            date_str = consultation.started_at.strftime("%d.%m.%Y %H:%M")
            
            header_text = (
                f"🗃 #{archive_id}\n"
                f"📅 {date_str}\n"
                f"👤 Клиент: {client_name}\n"
                f"🌸 Флорист: {florist_name}\n"
                f"🎯 Тема: {consultation.theme or 'Консультация'}\n"
                f"⭐ Рейтинг: {self._get_consultation_rating(consultation)}\n"
                f"{'='*30}"
            )
            
            # Отправляем заголовок в архивный канал
            await self.bot.send_message(settings.ARCHIVE_CHANNEL_ID, header_text)
            
            # Пересылаем все сообщения
            for message in messages:
                try:
                    if message.photo_file_id:
                        await self.bot.send_photo(
                            settings.ARCHIVE_CHANNEL_ID,
                            message.photo_file_id,
                            caption=f"👤 {message.sender.first_name}: {message.message_text or ''}"
                        )
                    elif message.message_text:
                        sender_name = message.sender.first_name or "Пользователь"
                        await self.bot.send_message(
                            settings.ARCHIVE_CHANNEL_ID,
                            f"👤 {sender_name}: {message.message_text}"
                        )
                except Exception as e:
                    print(f"Error archiving message {message.id}: {e}")
            
            # Завершающий разделитель
            await self.bot.send_message(settings.ARCHIVE_CHANNEL_ID, "📁 Конец архива\n" + "="*40)
            
            return archive_id
            
        except Exception as e:
            print(f"Error archiving consultation: {e}")
            return ""
    
    def _get_consultation_rating(self, consultation: Consultation) -> str:
        """Получить рейтинг консультации"""
        # TODO: реализовать после добавления отзывов
        return "Не оценено"
    
    async def restore_consultation_from_archive(self, chat_id: int, archive_id: str) -> bool:
        """Восстановление консультации из архива"""
        try:
            # TODO: Поиск сообщений в архивном канале по хештегу
            # Пока заглушка - в реальности нужно искать по archive_id в канале
            await self.bot.send_message(
                chat_id, 
                f"🔍 Поиск архива {archive_id}...\n"
                "⚠️ Функция восстановления в разработке"
            )
            return True
        except Exception as e:
            print(f"Error restoring consultation: {e}")
            return False