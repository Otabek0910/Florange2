import asyncio
import os
from dotenv import load_dotenv

# Загружаем .env до импортов, которые читают переменные
load_dotenv()

from aiogram import Bot, Dispatcher
from app.handlers import start, catalog, cart

async def main():
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)

    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
