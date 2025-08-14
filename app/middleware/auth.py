from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Update, User as TgUser

from app.database.database import get_session
from app.services.user_service import UserService

class AuthMiddleware(BaseMiddleware):
    """Middleware для предоставления сервисов и обновления активности флористов"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """Добавляет user_service и пользователя в контекст + обновляет активность флористов"""
        user: TgUser = data.get("event_from_user")
        if not user:
            return await handler(event, data)
        
        # Создаем сессию для middleware
        async for session in get_session():
            user_service = UserService(session)
            
            try:
                # ТОЛЬКО ищем пользователя, НЕ СОЗДАЕМ
                app_user = await user_service.user_repo.get_by_tg_id(str(user.id))
                
                # 🆕 Обновляем активность флориста автоматически
                if app_user and app_user.role.value in ['florist', 'owner']:
                    await self._update_florist_activity(app_user.id, session)
                
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
    
    async def _update_florist_activity(self, user_id: int, session):
        """Обновить активность флориста"""
        try:
            from app.services import FloristService
            florist_service = FloristService(session)
            await florist_service.update_activity(user_id)
            await session.commit()
        except Exception as e:
            print(f"Error updating florist activity: {e}")
            # Не падаем, если не получилось обновить активность