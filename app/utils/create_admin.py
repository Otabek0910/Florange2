import asyncio
import sys
from sqlalchemy import select, update
from app.database import get_session
from app.models import User, RoleEnum

async def create_super_admin():
    """Создать первого супер-админа (владельца)"""
    
    if len(sys.argv) < 2:
        print("Использование: python -m app.utils.create_admin <telegram_id>")
        print("Пример: python -m app.utils.create_admin 123456789")
        return
    
    telegram_id = sys.argv[1]
    
    try:
        async for session in get_session():
            # Проверяем, есть ли уже пользователь
            result = await session.execute(select(User).where(User.tg_id == telegram_id))
            user = result.scalars().first()
            
            if user:
                # Обновляем роль существующего пользователя
                await session.execute(
                    update(User)
                    .where(User.tg_id == telegram_id)
                    .values(role=RoleEnum.owner)
                )
                print(f"✅ Пользователь {telegram_id} ({user.first_name}) назначен владельцем")
            else:
                # Создаем нового пользователя-владельца
                new_user = User(
                    tg_id=telegram_id,
                    first_name="Admin",
                    lang="ru",
                    role=RoleEnum.owner
                )
                session.add(new_user)
                print(f"✅ Создан новый пользователь-владелец {telegram_id}")
            
            await session.commit()
            
    except Exception as e:
        print(f"❌ Ошибка создания админа: {e}")

if __name__ == "__main__":
    asyncio.run(create_super_admin())