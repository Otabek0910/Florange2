# add_settings.py - добавить дефолтные настройки
import asyncio
from app.database import get_session
from app.models import Settings

async def add_default_settings():
    """Добавить дефолтные настройки в БД"""
    
    try:
        async for session in get_session():
            # Проверяем, есть ли уже настройки
            from sqlalchemy import select
            
            existing = await session.execute(select(Settings))
            if existing.scalars().first():
                print("✅ Настройки уже существуют")
                return
            
            # Добавляем дефолтные настройки
            settings = [
                Settings(key="florist_registration_open", value="false"),
                Settings(key="owner_registration_open", value="false")
            ]
            
            for setting in settings:
                session.add(setting)
            
            await session.commit()
            print("✅ Дефолтные настройки добавлены")
            
    except Exception as e:
        print(f"❌ Ошибка добавления настроек: {e}")

if __name__ == "__main__":
    asyncio.run(add_default_settings())