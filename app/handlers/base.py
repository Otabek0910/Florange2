from typing import Optional, Tuple
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services import UserService
from app.models import User
from app.exceptions import UserNotFoundError

class BaseHandler:
    """Базовый класс с общей функциональностью для всех handlers"""
    
    @staticmethod
    async def get_user_context(
        session: AsyncSession, 
        tg_id: int
    ) -> Tuple[Optional[User], str]:
        """
        Получить пользователя и язык через сервис
        Returns: (user, lang)
        """
        user_service = UserService(session)
        try:
            user = await user_service.get_user_by_tg_id(str(tg_id))
            return user, user.lang or "ru"
        except UserNotFoundError:
            return None, "ru"
    
    @staticmethod
    async def with_session(func):
        """Декоратор для автоматического управления сессией"""
        async def wrapper(*args, **kwargs):
            async for session in get_session():
                try:
                    kwargs['session'] = session
                    result = await func(*args, **kwargs)
                    await session.commit()
                    return result
                except Exception as e:
                    await session.rollback()
                    raise e
        return wrapper
    
    @staticmethod
    async def delete_messages_range(
        bot, 
        chat_id: int, 
        start_msg_id: int, 
        count: int = 20
    ):
        """Удалить диапазон сообщений"""
        deleted = 0
        for i in range(count):
            try:
                await bot.delete_message(chat_id, start_msg_id - i)
                deleted += 1
            except:
                continue
        return deleted