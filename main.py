import asyncio
import logging
import os
import sys
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.handlers import start, catalog, cart, checkout, admin, orders, consultation
from app.middleware.auth import AuthMiddleware
from app.database import init_db

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

load_dotenv()

async def main():
    """Главная функция приложения"""
    # Инициализация БД
    await init_db()
    
    # Загрузка seed данных если передан аргумент --seed
    if "--seed" in sys.argv:
        from app.utils.seed import load_seed_data
        await load_seed_data()
        return

    # Создание бота и диспетчера
    storage = MemoryStorage()
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher(storage=storage)

    # 🆕 Подключение AuthMiddleware для автоматического создания пользователей
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Подключение роутеров
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(checkout.router)
    dp.include_router(admin.router)
    dp.include_router(orders.router)
    dp.include_router(consultation.router)

    print("🌸 Florange Bot запущен с AuthMiddleware...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())