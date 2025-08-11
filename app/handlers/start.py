from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select
from app.database import get_session
from app.models import User

router = Router()

@router.message(Command("start"))
async def start_cmd(message: types.Message):
    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == str(message.from_user.id)))
        user = result.scalars().first()
        if not user:
            session.add(User(tg_id=str(message.from_user.id), first_name=message.from_user.first_name))
            await session.commit()

    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🛍 Каталог"), types.KeyboardButton(text="🛒 Корзина")],
            [types.KeyboardButton(text="📦 Мои заказы")]
        ],
        resize_keyboard=True
    )
    await message.answer("Добро пожаловать в Florange! 🌸", reply_markup=kb)
