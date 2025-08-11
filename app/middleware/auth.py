from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Update, User as TgUser

from app.database import get_session
from app.services.user_service import UserService

class AuthMiddleware(BaseMiddleware):
    """Middleware для аутентификации пользователей"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """Добавляет пользователя в контекст"""
        user: TgUser = data.get("event_from_user")
        if not user:
            return await handler(event, data)
        
        # Создаем сессию для middleware
        async for session in get_session():
            user_service = UserService(session)
            
            try:
                # Получаем или создаем пользователя
                app_user = await user_service.get_or_create_user(
                    tg_id=str(user.id),
                    first_name=user.first_name or "",
                    lang="ru"  # default language, может быть изменен при регистрации
                )
                await session.commit()
                
                # Добавляем в контекст
                data["user"] = app_user
                data["user_service"] = user_service
                data["session"] = session
                
            except Exception as e:
                # Логируем ошибку, но не блокируем обработку
                print(f"AuthMiddleware error: {e}")
                data["user"] = None
                data["user_service"] = user_service
                data["session"] = session
            
            return await handler(event, data)