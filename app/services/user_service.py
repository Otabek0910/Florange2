from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import UserRepository, SettingsRepository
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.models import User, RoleEnum
from app.exceptions import UserNotFoundError, PermissionDeniedError

class UserService:
    """Сервис для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.settings_repo = SettingsRepository(session)
    
    async def get_or_create_user(self, tg_id: str, first_name: str, lang: str = "ru") -> User:
        """Получить или создать пользователя"""
        user = await self.user_repo.get_by_tg_id(tg_id)
        if not user:
            user_data = UserCreate(
                tg_id=tg_id,
                first_name=first_name,
                lang=lang,
                role=RoleEnum.client
            )
            user = User(**user_data.dict())
            user = await self.user_repo.create(user)
        return user
    
    async def get_user_by_tg_id(self, tg_id: str) -> User:
        """Получить пользователя по Telegram ID"""
        user = await self.user_repo.get_by_tg_id(tg_id)
        if not user:
            raise UserNotFoundError(tg_id)
        return user
    
    async def update_user(self, tg_id: str, data: UserUpdate) -> User:
        """Обновить данные пользователя"""
        user = await self.get_user_by_tg_id(tg_id)
        updated_user = await self.user_repo.update(user.id, data.dict(exclude_unset=True))
        return updated_user
    
    async def check_role_registration_open(self, role: str) -> bool:
        """Проверить открыта ли регистрация для роли"""
        key = f"{role}_registration_open"
        return await self.settings_repo.get_bool_value(key, False)
    
    async def create_role_request(self, tg_id: str, requested_role: str, reason: str) -> None:
        """Создать заявку на роль"""
        user = await self.get_user_by_tg_id(tg_id)
        
        if not await self.check_role_registration_open(requested_role):
            raise PermissionDeniedError("Registration for this role is closed")
        
        await self.user_repo.create_role_request(user.id, requested_role, reason)
    
    async def get_admins(self) -> list[User]:
        """Получить список администраторов"""
        return await self.user_repo.get_by_role(RoleEnum.owner)