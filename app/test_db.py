# test_db.py - тест БД и моделей
import asyncio
from app.database import init_db, get_session
from app.models import User, RoleEnum, Settings

async def test_database():
    """Тест базы данных без Telegram"""
    
    try:
        print("🔧 Инициализация БД...")
        await init_db()
        print("✅ БД инициализирована")
        
        async for session in get_session():
            # Тест создания пользователя
            print("👤 Создание тестового пользователя...")
            user = User(
                tg_id="12345",
                first_name="Test User",
                lang="ru",
                role=RoleEnum.client
            )
            session.add(user)
            await session.commit()
            print("✅ Пользователь создан")
            
            # Тест настроек
            print("⚙️ Проверка настроек...")
            from sqlalchemy import select
            result = await session.execute(select(Settings))
            settings = result.scalars().all()
            print(f"✅ Найдено {len(settings)} настроек")
            
            for setting in settings:
                print(f"  {setting.key} = {setting.value}")
        
        print("🎉 Все тесты БД прошли успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования БД: {e}")

if __name__ == "__main__":
    asyncio.run(test_database())