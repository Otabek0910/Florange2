from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import select, update
from app.database import get_session
from app.models import User
from app.translate import t

router = Router()

@router.message(Command("start"))
async def start_cmd(message: types.Message):
    # Проверяем пользователя
    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == str(message.from_user.id)))
        user = result.scalars().first()

        if not user:
            session.add(User(tg_id=str(message.from_user.id), first_name=message.from_user.first_name, lang=None))
            await session.commit()

    # Выбор языка
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [types.InlineKeyboardButton(text="🇺🇿 Oʻzbekcha", callback_data="lang_uz")]
    ])
    await message.answer(t("ru", "start_choose_lang") + "\n" + t("uz", "start_choose_lang"), reply_markup=kb)

@router.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]

    async for session in get_session():
        await session.execute(update(User).where(User.tg_id == str(callback.from_user.id)).values(lang=lang))
        await session.commit()

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t(lang, "menu_catalog"), callback_data="open_catalog")],
        [types.InlineKeyboardButton(text=t(lang, "menu_cart"), callback_data="open_cart")],
        [types.InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data="my_orders")]
    ])

    if lang == "ru":
        text = t(lang, "lang_saved_ru")
    else:
        text = t(lang, "lang_saved_uz")

    text += f"\n{t(lang, 'menu_title')}"
    await callback.message.edit_text(text, reply_markup=kb)
