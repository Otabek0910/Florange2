# В main.py обновить создание бота:

import asyncio, os, sys
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

from app.handlers import start, catalog, cart, checkout, orders, admin
from app.database import init_db

load_dotenv()

async def main():
    # Инициализация БД
    await init_db()
    
    # Добавление дефолтных настроек
    print("📋 Проверка настроек...")
    try:
        from add_settings import add_default_settings
        await add_default_settings()
    except Exception as e:
        print(f"⚠️ Не удалось добавить настройки: {e}")
    
    # Загрузка seed данных если передан аргумент --seed
    if "--seed" in sys.argv:
        from app.utils.seed import load_seed_data
        await load_seed_data()
        return

    # Создание бота с обработкой ошибок сети
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("❌ BOT_TOKEN не найден в .env файле")
        return
    
    try:
        bot = Bot(token=bot_token)
        dp = Dispatcher()

        dp.include_router(start.router)
        dp.include_router(catalog.router)
        dp.include_router(cart.router)
        dp.include_router(checkout.router)
        dp.include_router(orders.router)
        dp.include_router(admin.router)

        print("🤖 Проверка подключения к Telegram...")
        me = await bot.get_me()
        print(f"✅ Бот авторизован: {me.first_name} (@{me.username})")
        
        print("🚀 Бот запущен и готов к работе!")
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        print("\n🔍 Возможные решения:")
        print("1. Проверьте интернет-соединение")
        print("2. Проверьте токен бота в .env")
        print("3. Попробуйте использовать VPN/прокси")
        print("4. Запустите тест БД: python test_db.py")
        
        # Предлагаем тест БД
        print("\n🧪 Хотите протестировать только БД? (y/n)")
        # В продакшене можно убрать input
        try:
            choice = input().lower()
            if choice == 'y':
                await test_database_only()
        except:
            pass

async def test_database_only():
    """Тест только базы данных"""
    print("\n🔧 Тестирование БД...")
    try:
        from app.models import User, RoleEnum
        from app.database import get_session
        
        async for session in get_session():
            # Создаем тестового пользователя
            test_user = User(
                tg_id="test_123",
                first_name="Test User",
                lang="ru",
                role=RoleEnum.client
            )
            session.add(test_user)
            await session.commit()
            print("✅ Тестовый пользователь создан")
            
            # Проверяем настройки
            from app.models import Settings
            from sqlalchemy import select
            settings_result = await session.execute(select(Settings))
            settings = settings_result.scalars().all()
            print(f"✅ Найдено {len(settings)} настроек")
            
        print("🎉 База данных работает корректно!")
        
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")

if __name__ == "__main__":
    asyncio.run(main())