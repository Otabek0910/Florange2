from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Update, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

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
        
        async for session in get_session():
            user_service = UserService(session)
            app_user = await user_service.get_or_create_user(
                tg_id=str(user.id),
                first_name=user.first_name or "",
                lang="ru"  # default language
            )
            data["user"] = app_user
            data["user_service"] = user_service
            
        return await handler(event, data)