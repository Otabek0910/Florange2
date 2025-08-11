from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from app.models import User, RoleEnum, RoleRequest, RequestStatusEnum

class UserRepository(BaseRepository[User]):
    """Репозиторий для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)
    
    async def get_by_tg_id(self, tg_id: str) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        result = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        return result.scalars().first()
    
    async def get_by_role(self, role: RoleEnum) -> list[User]:
        """Получить пользователей по роли"""
        result = await self.session.execute(
            select(User).where(User.role == role)
        )
        return result.scalars().all()
    
    async def create_role_request(self, user_id: int, requested_role: str, reason: str) -> RoleRequest:
        """Создать заявку на роль"""
        request = RoleRequest(
            user_id=user_id,
            requested_role=requested_role,
            reason=reason,
            status=RequestStatusEnum.pending
        )
        return await self.create(request)
    
    async def get_pending_requests(self) -> list[RoleRequest]:
        """Получить ожидающие заявки"""
        result = await self.session.execute(
            select(RoleRequest).where(RoleRequest.status == RequestStatusEnum.pending)
        )
        return result.scalars().all()