import asyncio, os, sys
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

from app.handlers import start, catalog, cart, checkout
from app.database import init_db

load_dotenv()

async def main():
    # Инициализация БД
    await init_db()
    
    # Загрузка seed данных если передан аргумент --seed
    if "--seed" in sys.argv:
        from app.utils.seed import load_seed_data
        await load_seed_data()
        return

    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(checkout.router)

    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())