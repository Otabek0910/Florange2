from aiogram import Bot, Dispatcher
from app.handlers import start
import asyncio
import os

async def main():
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher()
    dp.include_router(start.router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
