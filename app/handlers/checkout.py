from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
import os, re
from decimal import Decimal

from app.database import get_session
from app.models import User, Product, Order, OrderItem  # предполагаются в твоём models.py
from app.utils.cart import get_cart, clear_cart
from app.translate import t

router = Router()

PHONE_RE = re.compile(r"^\+?\d[\d\s\-()]{5,}$")

class Checkout(StatesGroup):
    ASK_ADDRESS = State()
    ASK_PHONE = State()
    ASK_DATETIME = State()
    CONFIRM = State()

async def _get_user_lang(session, tg_id: int) -> str:
    res = await session.execute(select(User).where(User.tg_id == str(tg_id)))
    user = res.scalars().first()
    return (user.lang or "ru") if user else "ru"

@router.callback_query(F.data == "checkout")
async def checkout_start(callback: types.CallbackQuery, state: FSMContext):
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)

    await state.clear()
    await state.set_state(Checkout.ASK_ADDRESS)
    await callback.message.edit_text(t(lang, "ask_address"))
    await callback.answer()

@router.message(Checkout.ASK_ADDRESS)
async def ask_phone(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await state.set_state(Checkout.ASK_PHONE)

    # язык
    async for session in get_session():
        lang = await _get_user_lang(session, message.from_user.id)
    await message.answer(t(lang, "ask_phone"))

@router.message(Checkout.ASK_PHONE)
async def ask_datetime(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    async for session in get_session():
        lang = await _get_user_lang(session, message.from_user.id)

    if not PHONE_RE.match(phone):
        await message.answer(t(lang, "invalid_phone"))
        return

    await state.update_data(phone=phone)
    await state.set_state(Checkout.ASK_DATETIME)
    await message.answer(t(lang, "ask_datetime"))

@router.message(Checkout.ASK_DATETIME)
async def confirm_order(message: types.Message, state: FSMContext):
    slot = message.text.strip()
    await state.update_data(slot=slot)

    async for session in get_session():
        lang = await _get_user_lang(session, message.from_user.id)

    # собрать корзину
    cart = get_cart(message.from_user.id)
    if not cart:
        await message.answer(t(lang, "cart_empty"))
        await state.clear()
        return

    # посчитать итого
    total = Decimal("0")
    lines = []
    async for session in get_session():
        for pid, qty in cart.items():
            product = await session.get(Product, int(pid))
            if not product:
                continue
            price = Decimal(str(product.price))
            qty_d = Decimal(str(qty))
            total += price * qty_d
            name = product.name_ru if lang == "ru" else product.name_uz
            lines.append(f"{name} — {qty} × {price} {t(lang,'currency')}")

    data = await state.get_data()
    text = (
        f"{t(lang, 'confirm_order')}\n\n"
        + "\n".join(lines)
        + t(lang, "total_line", total=total, currency=t(lang, "currency"))
        + f"\n\n📍 {data['address']}\n📞 {data['phone']}\n🗓 {data['slot']}"
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ OK", callback_data="confirm_ok")],
        [types.InlineKeyboardButton(text="↩️ "+t(lang, "cart_clear"), callback_data="confirm_cancel")],
    ])
    await state.set_state(Checkout.CONFIRM)
    await message.answer(text, reply_markup=kb)

@router.callback_query(Checkout.CONFIRM, F.data == "confirm_ok")
async def create_order(callback: types.CallbackQuery, state: FSMContext):
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)

    cart = get_cart(callback.from_user.id)
    if not cart:
        await callback.message.edit_text(t(lang, "cart_empty"))
        await state.clear()
        await callback.answer()
        return

    data = await state.get_data()

    # создаём заказ + позиции
    async for session in get_session():
        # найдём/подтянем пользователя
        res = await session.execute(select(User).where(User.tg_id == str(callback.from_user.id)))
        user = res.scalars().first()

        order = Order(
            user_id=user.id if user else None,
            address=data["address"],
            phone=data["phone"],
            slot_at=data["slot"],
            status="new",
        )
        session.add(order)
        await session.flush()  # получим order.id

        total = Decimal("0")
        for pid, qty in cart.items():
            product = await session.get(Product, int(pid))
            if not product:
                continue
            price = Decimal(str(product.price))
            qty_d = Decimal(str(qty))
            total += price * qty_d

            oi = OrderItem(
                order_id=order.id,
                product_id=product.id,
                qty=int(qty),
                price=price,
            )
            session.add(oi)

        order.total_price = total  # поле предполагается в модели
        await session.commit()

        clear_cart(callback.from_user.id)

        # уведомление флористам
        florist_channel = os.getenv("FLORIST_CHANNEL_ID")
        if florist_channel:
            lines = []
            for pid, qty in cart.items():
                p = await session.get(Product, int(pid))
                if p:
                    lines.append(f"{p.name} — {qty} × {p.price} {t(lang,'currency')}")
            text = (
                f"🆕 Заказ #{order.id}\n"
                + "\n".join(lines)
                + t(lang, "total_line", total=order.total_price, currency=t(lang, "currency"))
                + f"\n\n📍 {order.address}\n📞 {order.phone}\n🗓 {order.slot_at}"
            )

            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{order.id}")],
                [types.InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{order.id}")],
            ])
            await callback.bot.send_message(chat_id=int(florist_channel), text=text, reply_markup=kb)

    await callback.message.edit_text(t(lang, "order_created"))
    await state.clear()
    await callback.answer()

@router.callback_query(Checkout.CONFIRM, F.data == "confirm_cancel")
async def cancel_confirm(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
    await callback.message.edit_text(t(lang, "cart_cleared"))
    await callback.answer()

# Колбэки флорист-канала
@router.callback_query(F.data.startswith("accept_"))
async def florist_accept(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    async for session in get_session():
        # обновляем статус
        order = await session.get(Order, order_id)
        if order:
            order.status = "accepted"
            await session.commit()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Принято")

@router.callback_query(F.data.startswith("cancel_"))
async def florist_cancel(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    async for session in get_session():
        order = await session.get(Order, order_id)
        if order:
            order.status = "canceled"
            await session.commit()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("❌ Отменено")
