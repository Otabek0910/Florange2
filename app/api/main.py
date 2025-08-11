import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from dotenv import load_dotenv

from app.handlers import start

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook/telegram"
WEBHOOK_URL = os.getenv("WEBHOOK_URL") + WEBHOOK_PATH  # например, https://yourdomain.com/webhook/telegram

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
dp.include_router(start.router)

app = FastAPI(title="Florange API")

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)

@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()

@app.post(WEBHOOK_PATH)
async def telegram_webhook(update: dict):
    telegram_update = Update(**update)
    await dp.feed_update(bot, telegram_update)
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok"}
