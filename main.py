import asyncio
import os
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from app.handlers import start, catalog




load_dotenv()

async def main():
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher()
    dp.include_router(start.router)
    print("Бот запущен...")
    await dp.start_polling(bot)

    dp.include_router(start.router)
    dp.include_router(catalog.router)

if __name__ == "__main__":
    asyncio.run(main())
