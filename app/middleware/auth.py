from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Update, User as TgUser

from app.database import get_session
from app.services.user_service import UserService

class AuthMiddleware(BaseMiddleware):
    """Middleware для предоставления сервисов (НЕ создает пользователей автоматически)"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """Добавляет user_service и пользователя в контекст (если найден)"""
        user: TgUser = data.get("event_from_user")
        if not user:
            return await handler(event, data)
        
        # Создаем сессию для middleware
        async for session in get_session():
            user_service = UserService(session)
            
            try:
                # ТОЛЬКО ищем пользователя, НЕ СОЗДАЕМ
                app_user = await user_service.user_repo.get_by_tg_id(str(user.id))
                
                # Добавляем в контекст
                data["user"] = app_user  # None если не найден
                data["user_service"] = user_service
                data["session"] = session
                data["tg_user"] = user  # Добавляем Telegram данные
                
            except Exception as e:
                # Логируем ошибку, но не блокируем обработку
                print(f"AuthMiddleware error: {e}")
                data["user"] = None
                data["user_service"] = user_service
                data["session"] = session
                data["tg_user"] = user
            
            return await handler(event, data)