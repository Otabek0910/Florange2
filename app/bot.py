# /project/app/bot.py
import asyncio
import logging
import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from app.translate import t
import os

# =============================
# НАСТРОЙКИ
# =============================
TOKEN = os.getenv("BOT_TOKEN", "ТОКЕН_ТВОЕГО_БОТА")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "1234")
DB_NAME = os.getenv("DB_NAME", "Florange")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

logging.basicConfig(level=logging.INFO)

# =============================
# Подключение к базе данных
# =============================
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT
    )

# Создание таблицы пользователей
async def init_db(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            language TEXT DEFAULT 'ru'
        )
        """)

# =============================
# ФУНКЦИИ БД
# =============================
async def get_user(pool, user_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

async def add_user(pool, user_id, username, first_name, last_name, language="ru"):
    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, language)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id) DO UPDATE SET language = EXCLUDED.language
        """, user_id, username, first_name, last_name, language)

async def update_language(pool, user_id, language):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET language = $1 WHERE user_id = $2", language, user_id)

# =============================
# КНОПКИ
# =============================
def language_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="lang_uz")]
    ])
    return kb

def main_menu(lang):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("menu_flowers", lang), callback_data="menu_flowers")],
        [InlineKeyboardButton(text=t("menu_bouquets", lang), callback_data="menu_bouquets")],
        [InlineKeyboardButton(text=t("menu_vip", lang), callback_data="menu_vip")],
        [InlineKeyboardButton(text=t("menu_cards", lang), callback_data="menu_cards")],
        [InlineKeyboardButton(text=t("menu_wrapping", lang), callback_data="menu_wrapping")],
        [InlineKeyboardButton(text=t("menu_plants", lang), callback_data="menu_plants")],
        [InlineKeyboardButton(text=t("menu_toys_perfume", lang), callback_data="menu_toys_perfume")],
    ])
    return kb

# =============================
# ОБРАБОТЧИКИ
# =============================
async def cmd_start(message: Message, pool):
    user = await get_user(pool, message.from_user.id)
    if not user:
        await add_user(pool, message.from_user.id, message.from_user.username,
                       message.from_user.first_name, message.from_user.last_name)
        sent = await message.answer(t("start_message", "ru"), reply_markup=language_keyboard())
        await asyncio.sleep(0.5)
        await message.delete()
        return sent
    else:
        lang = user["language"]
        sent = await message.answer(t("menu_main", lang), reply_markup=main_menu(lang))
        await asyncio.sleep(0.5)
        await message.delete()
        return sent

async def set_language(callback: CallbackQuery, pool):
    lang_code = callback.data.split("_")[1]
    await update_language(pool, callback.from_user.id, lang_code)
    await callback.message.delete()
    await callback.message.answer(t("menu_main", lang_code), reply_markup=main_menu(lang_code))

async def menu_handler(callback: CallbackQuery, pool):
    user = await get_user(pool, callback.from_user.id)
    lang = user["language"] if user else "ru"
    await callback.message.delete()
    await callback.message.answer(f"📌 {t(callback.data, lang)} — в разработке", reply_markup=main_menu(lang))

# =============================
# MAIN
# =============================
async def main():
    bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    pool = await create_db_pool()
    await init_db(pool)

    dp.message.register(lambda msg: cmd_start(msg, pool), CommandStart())
    dp.callback_query.register(lambda cb: set_language(cb, pool), F.data.startswith("lang_"))
    dp.callback_query.register(lambda cb: menu_handler(cb, pool), F.data.startswith("menu_"))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
