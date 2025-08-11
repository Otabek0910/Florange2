from aiogram import Router, types, F
from sqlalchemy import select
from decimal import Decimal

from app.database import get_session
from app.models import Product, User
from app.utils.cart import add_to_cart, get_cart, clear_cart
from app.translate import t

router = Router()

async def _get_user_lang(session, tg_id: int) -> str:
    res = await session.execute(select(User).where(User.tg_id == str(tg_id)))
    user = res.scalars().first()
    return (user.lang or "ru") if user else "ru"

# Добавление товара в корзину
@router.callback_query(F.data.startswith("add_"))
async def add_product(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    add_to_cart(callback.from_user.id, pid)
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
    await callback.answer(t(lang, "item_added"), show_alert=False)

# Открыть корзину
@router.callback_query(F.data == "open_cart")
async def show_cart(callback: types.CallbackQuery):
    cart_data = get_cart(callback.from_user.id)

    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)

        if not cart_data:
            await callback.message.edit_text(t(lang, "cart_empty"))
            await callback.answer()
            return

        lines = [t(lang, "cart_title"), ""]
        total = Decimal("0")

        for pid, qty in cart_data.items():
            product = await session.get(Product, int(pid))
            if product:
                price = Decimal(str(product.price))
                lines.append(f"{product.name} — {qty} × {price} {t(lang, 'currency')}")
                total += price * Decimal(str(qty))

        text = "\n".join(lines) + t(lang, "total_line", total=total, currency=t(lang, "currency"))

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t(lang, "cart_clear"), callback_data="clear_cart")],
        [types.InlineKeyboardButton(text=t(lang, "cart_checkout"), callback_data="checkout")],  # сам checkout обрабатывается в checkout.py
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# Очистить корзину
@router.callback_query(F.data == "clear_cart")
async def clear_cart_cb(callback: types.CallbackQuery):
    clear_cart(callback.from_user.id)
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
    await callback.message.edit_text(t(lang, "cart_cleared"))
    await callback.answer()
