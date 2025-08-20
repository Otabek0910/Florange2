# main.py - обновить импорты (заменить строки 1-18)
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.handlers import start, catalog, cart, checkout, admin, orders, consultation, florist
from app.middleware.auth import AuthMiddleware
from app.middleware.state_validation import StateValidationMiddleware, ConsultationCleanupMiddleware
from app.database.database import init_db

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

async def main():
    """Главная функция приложения"""
    
    # Валидация конфигурации
    config.validate()
    
    # Инициализация БД
    await init_db()
    
    # Загрузка seed данных если передан аргумент --seed
    if "--seed" in sys.argv:
        from app.utils.seed import load_seed_data
        await load_seed_data()
        return

    # Создание бота и диспетчера
    storage = MemoryStorage()
    bot = Bot(token=config.BOT_TOKEN)  # Используем config вместо os.getenv
    dp = Dispatcher(storage=storage)

    # Middleware
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(StateValidationMiddleware())
    dp.callback_query.middleware(StateValidationMiddleware())
    dp.message.middleware(ConsultationCleanupMiddleware(cleanup_frequency=100))
    print("✅ Middleware зарегистрированы")

    # Подключение роутеров
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(checkout.router)
    dp.include_router(admin.router)
    dp.include_router(orders.router)
    dp.include_router(consultation.router)
    dp.include_router(florist.router)
    
    print("🌸 Florange Bot запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

# Действия:
# 1. Заменить импорты в main.py
# 2. Убрать load_dotenv() 
# 3. Использовать config.BOT_TOKEN