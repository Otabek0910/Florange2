from aiogram import Router, types, F
from sqlalchemy import select
from app.database import get_session
from app.models import Product, User
from app.utils.cart import add_to_cart, get_cart, clear_cart
from app.translate import t

router = Router()

@router.callback_query(F.data.startswith("add_"))
async def add_product(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])

    async for session in get_session():
        user = await session.execute(select(User).where(User.tg_id == str(callback.from_user.id)))
        user_lang = user.scalars().first().lang or "ru"

    add_to_cart(callback.from_user.id, pid)
    await callback.answer(t(user_lang, "item_added"), show_alert=False)

@router.callback_query(F.data == "open_cart")
async def show_cart(callback: types.CallbackQuery):
    async for session in get_session():
        user = await session.execute(select(User).where(User.tg_id == str(callback.from_user.id)))
        user_lang = user.scalars().first().lang or "ru"

    cart_data = get_cart(callback.from_user.id)
    if not cart_data:
        await callback.message.edit_text(t(user_lang, "cart_empty"))
        return

    text = f"{t(user_lang, 'cart_title')}\n\n"
    total = 0

    async for session in get_session():
        for pid, qty in cart_data.items():
            product = await session.get(Product, int(pid))
            if product:
                text += f"{product.name} — {qty} × {product.price} сум\n"
                total += product.price * qty

    text += f"\n<b>Итого:</b> {total} сум"

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t(user_lang, "cart_clear"), callback_data="clear_cart")],
        [types.InlineKeyboardButton(text=t(user_lang, "cart_checkout"), callback_data="checkout")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "clear_cart")
async def clear_cart_cb(callback: types.CallbackQuery):
    async for session in get_session():
        user = await session.execute(select(User).where(User.tg_id == str(callback.from_user.id)))
        user_lang = user.scalars().first().lang or "ru"

    clear_cart(callback.from_user.id)
    await callback.message.edit_text(t(user_lang, "cart_cleared"))
