from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from decimal import Decimal
from datetime import datetime

from app.database import get_session
from app.services import UserService, CatalogService, OrderService, NotificationService
from app.schemas.order import OrderCreate
from app.utils.cart import get_cart, clear_cart
from app.utils.validators import validate_phone, validate_address
from app.translate import t
from app.exceptions import ProductNotFoundError, ValidationError
from app.models import RoleEnum

router = Router()

class Checkout(StatesGroup):
    ASK_ADDRESS = State()
    ASK_PHONE = State()
    ASK_DATETIME = State()
    CONFIRM = State()

async def _get_user_and_lang(session, tg_id: int):
    """Получить пользователя и язык через сервис"""
    user_service = UserService(session)
    try:
        user = await user_service.get_user_by_tg_id(str(tg_id))
        return user, user.lang or "ru"
    except:
        return None, "ru"

@router.callback_query(F.data == "checkout")
async def checkout_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало оформления заказа"""
    # Проверяем корзину
    cart_data = get_cart(callback.from_user.id)
    if not cart_data:
        async for session in get_session():
            user, lang = await _get_user_and_lang(session, callback.from_user.id)
        await callback.message.edit_text(t(lang, "cart_empty"))
        await callback.answer()
        return

    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)

    await state.clear()
    await state.set_state(Checkout.ASK_ADDRESS)
    await callback.message.edit_text(t(lang, "ask_address"))
    await callback.answer()

@router.message(Checkout.ASK_ADDRESS)
async def process_address(message: types.Message, state: FSMContext):
    """Обработка адреса доставки"""
    address = message.text.strip()
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)

    # Валидация адреса
    if not validate_address(address):
        await message.answer(t(lang, "invalid_address"))
        return

    await state.update_data(address=address)
    await state.set_state(Checkout.ASK_PHONE)
    await message.answer(t(lang, "ask_phone"))

@router.message(Checkout.ASK_PHONE)
async def process_phone(message: types.Message, state: FSMContext):
    """Обработка контактного телефона"""
    phone = message.text.strip()
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)

    # Валидация телефона
    if not validate_phone(phone):
        await message.answer(t(lang, "invalid_phone"))
        return

    await state.update_data(phone=phone)
    await state.set_state(Checkout.ASK_DATETIME)
    await message.answer(t(lang, "ask_datetime"))

@router.message(Checkout.ASK_DATETIME)
async def process_datetime(message: types.Message, state: FSMContext):
    """Обработка времени доставки"""
    slot_text = message.text.strip()
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)

    await state.update_data(slot_text=slot_text)

    # Получаем корзину и рассчитываем итого
    cart = get_cart(message.from_user.id)
    if not cart:
        await message.answer(t(lang, "cart_empty"))
        await state.clear()
        return

    # Валидируем товары и считаем сумму
    async for session in get_session():
        catalog_service = CatalogService(session)
        
        total = Decimal("0")
        lines = []
        invalid_items = []
        
        for pid, qty in cart.items():
            try:
                product = await catalog_service.get_product(int(pid))
                price = Decimal(str(product.price))
                qty_d = Decimal(str(qty))
                line_total = price * qty_d
                total += line_total
                
                name = product.name_ru if lang == "ru" else product.name_uz
                lines.append(f"{name} — {qty} × {price} {t(lang,'currency')}")
                
            except ProductNotFoundError:
                invalid_items.append(pid)
                continue

    if invalid_items:
        await message.answer(t(lang, "cart_has_invalid_items"))
        await state.clear()
        return

    if not lines:
        await message.answer(t(lang, "cart_empty"))
        await state.clear()
        return

    # Формируем подтверждение заказа
    data = await state.get_data()
    text = (
        f"{t(lang, 'confirm_order')}\n\n"
        + "\n".join(lines)
        + t(lang, "total_line", total=total, currency=t(lang, "currency"))
        + f"\n\n📍 {data['address']}\n📞 {data['phone']}\n🗓 {data['slot_text']}"
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_ok")],
        [types.InlineKeyboardButton(text="❌ Отменить", callback_data="confirm_cancel")],
    ])
    
    await state.set_state(Checkout.CONFIRM)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(Checkout.CONFIRM, F.data == "confirm_ok")
async def create_order(callback: types.CallbackQuery, state: FSMContext):
    """Создание заказа"""
    cart = get_cart(callback.from_user.id)
    if not cart:
        async for session in get_session():
            user, lang = await _get_user_and_lang(session, callback.from_user.id)
        await callback.message.edit_text(t(lang, "cart_empty"))
        await state.clear()
        await callback.answer()
        return

    data = await state.get_data()

    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.message.edit_text(t(lang, "user_not_found"))
            await state.clear()
            await callback.answer()
            return

        try:
            # Создаем заказ через сервис
            order_service = OrderService(session)
            
            order_data = OrderCreate(
                user_id=user.id,
                address=data["address"],
                phone=data["phone"],
                comment=f"Время доставки: {data['slot_text']}"
            )
            
            order = await order_service.create_order(
                user_id=user.id,
                cart_items=cart,
                order_data=order_data
            )
            
            await session.commit()
            
            # Очищаем корзину
            clear_cart(callback.from_user.id)
            
            # Уведомляем флористов
            notification_service = NotificationService(callback.bot)
            user_service = UserService(session)
            
            # Получаем флористов и владельцев
            florists = await user_service.user_repo.get_by_role(RoleEnum.florist)
            owners = await user_service.user_repo.get_by_role(RoleEnum.owner)
            all_florists = florists + owners
            
            if all_florists:
                await notification_service.notify_florists_about_order(all_florists, order, lang)
            
            await callback.message.edit_text(
                f"{t(lang, 'order_created')}\n\n🆔 Заказ #{order.id}",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
                ])
            )
            
        except Exception as e:
            await callback.message.edit_text(f"Ошибка создания заказа: {str(e)}")
            
    await state.clear()
    await callback.answer()

@router.callback_query(Checkout.CONFIRM, F.data == "confirm_cancel")
async def cancel_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Отмена подтверждения заказа"""
    await state.clear()
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(
        t(lang, "order_cancelled"), 
        reply_markup=kb
    )
    await callback.answer()

# Колбэки для флористов (управление заказами)
@router.callback_query(F.data.startswith("accept_"))
async def florist_accept_order(callback: types.CallbackQuery):
    """Флорист принимает заказ"""
    order_id = int(callback.data.split("_")[1])
    
    async for session in get_session():
        order_service = OrderService(session)
        
        try:
            from app.models import OrderStatusEnum
            order = await order_service.update_order_status(order_id, OrderStatusEnum.accepted)
            await session.commit()
            
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("✅ Заказ принят")
            
        except Exception as e:
            await callback.answer(f"Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("cancel_order_"))
async def florist_cancel_order(callback: types.CallbackQuery):
    """Флорист отменяет заказ"""
    order_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        order_service = OrderService(session)
        
        try:
            from app.models import OrderStatusEnum
            order = await order_service.update_order_status(order_id, OrderStatusEnum.canceled)
            await session.commit()
            
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("❌ Заказ отменен")
            
        except Exception as e:
            await callback.answer(f"Ошибка: {str(e)}", show_alert=True)