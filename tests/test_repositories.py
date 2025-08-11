import pytest
from app.repositories.user import UserRepository
from app.models import User, RoleEnum

class TestUserRepository:
    """Тесты репозитория пользователей"""
    
    @pytest.mark.asyncio
    async def test_create_user(self, test_db):
        """Тест создания пользователя"""
        async for session in test_db():
            repo = UserRepository(session)
            
            user = User(
                tg_id="123456",
                first_name="Test User",
                lang="ru",
                role=RoleEnum.client
            )
            
            created_user = await repo.create(user)
            assert created_user.id is not None
            assert created_user.tg_id == "123456"
    
    @pytest.mark.asyncio
    async def test_get_by_tg_id(self, test_db):
        """Тест получения пользователя по Telegram ID"""
        async for session in test_db():
            repo = UserRepository(session)
            
            # Создаем пользователя
            user = User(tg_id="123456", first_name="Test", lang="ru")
            await repo.create(user)
            await session.commit()
            
            # Получаем пользователя
            found_user = await repo.get_by_tg_id("123456")
            assert found_user is not None
            assert found_user.tg_id == "123456"