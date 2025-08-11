import asyncio, os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

from app.handlers import start, catalog, cart
from app.handlers import checkout  # NEW

load_dotenv()

async def main():
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(checkout.router)  # NEW

    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
