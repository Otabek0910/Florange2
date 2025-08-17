# app/handlers/checkout.py - ПОЛНАЯ ЗАМЕНА

from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from decimal import Decimal
from datetime import datetime, timedelta
import calendar
from datetime import datetime

from app.database.database import get_session
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
    ASK_DATE = State()
    ASK_TIME = State()
    CONFIRM = State()

async def _get_user_and_lang(session, tg_id: int):
    """Получить пользователя и язык через сервис"""
    from app.services import UserService
    from app.exceptions import UserNotFoundError
    
    user_service = UserService(session)
    try:
        user = await user_service.get_user_by_tg_id(str(tg_id))
        return user, user.lang or "ru"
    except UserNotFoundError:
        return None, "ru"

@router.callback_query(F.data == "checkout")
async def checkout_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало оформления заказа"""
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
    
    # УПРОЩЕННЫЙ ЗАПРОС АДРЕСА - все в одном сообщении
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="📍 Отправить мою геопозицию", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.edit_text(
        "📍 <b>Укажите адрес доставки:</b>\n\n"
        "• Напишите адрес текстом (улица, дом, подъезд, квартира)\n"
        "• Или нажмите кнопку ниже для отправки геопозиции",
        parse_mode="HTML"
    )
    
    await callback.bot.send_message(
        callback.message.chat.id,
        "👇 Выберите удобный способ:",
        reply_markup=kb
    )
    await callback.answer()


@router.message(Checkout.ASK_ADDRESS, F.location)
async def process_location(message: types.Message, state: FSMContext):
    """Обработка геопозиции"""
    lat = message.location.latitude
    lon = message.location.longitude
    address = f"📍 Координаты: {lat:.6f}, {lon:.6f}"
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)

    await state.update_data(address=address, latitude=lat, longitude=lon)
    await _proceed_to_phone(message, state, user)

@router.message(Checkout.ASK_ADDRESS, F.text)
async def process_address_text(message: types.Message, state: FSMContext):
    """Обработка адреса текстом"""
    address = message.text.strip()
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)

    # УЛУЧШЕННАЯ ВАЛИДАЦИЯ АДРЕСА
    if len(address) < 10:
        await message.answer(
            "❌ <b>Адрес слишком короткий</b>\n\n"
            "Пожалуйста, укажите:\n"
            "• Название улицы\n"
            "• Номер дома\n"
            "• Подъезд/квартиру (если нужно)\n\n"
            "<i>Пример: ул. Мустакиллик, дом 15, кв. 25</i>",
            parse_mode="HTML"
        )
        return

    await state.update_data(address=address)
    await _proceed_to_phone(message, state, user)

async def _proceed_to_phone(message: types.Message, state: FSMContext, user):
    """Переход к вводу телефона"""
    await state.set_state(Checkout.ASK_PHONE)
    
    # Предлагаем использовать свой номер или ввести получателя
    user_phone = user.phone if user else None
    kb_rows = []
    
    if user_phone:
        kb_rows.append([types.InlineKeyboardButton(
            text=f"📱 Мой номер: {user_phone}", 
            callback_data=f"use_my_phone_{user_phone}"
        )])
    
    kb_rows.append([types.InlineKeyboardButton(
        text="📞 Указать номер получателя", 
        callback_data="enter_recipient_phone"
    )])
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await message.answer(
        "✅ Адрес получен!\n\n📞 <b>Контактный телефон:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("use_my_phone_"))
async def use_my_phone(callback: types.CallbackQuery, state: FSMContext):
    """Использовать свой номер"""
    phone = callback.data.replace("use_my_phone_", "")
    await state.update_data(phone=phone)
    await _ask_delivery_date(callback, state)

@router.callback_query(F.data == "enter_recipient_phone")
async def ask_recipient_phone(callback: types.CallbackQuery, state: FSMContext):
    """Просим ввести номер получателя"""
    await callback.message.edit_text(
        "📞 Введите номер телефона получателя:\n\n"
        "Пример: +998901234567"
    )
    await callback.answer()

@router.message(Checkout.ASK_PHONE)
async def process_phone(message: types.Message, state: FSMContext):
    """Обработка телефона"""
    phone = message.text.strip()
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)

    if not validate_phone(phone):
        await message.answer("❌ Неверный формат номера. Пример: +998901234567")
        return

    await state.update_data(phone=phone)
    await _ask_delivery_date_message(message, state)

async def _ask_delivery_date(callback: types.CallbackQuery, state: FSMContext):
    """Показать календарь для выбора даты"""
    await state.set_state(Checkout.ASK_DATE)
    
    # Создаем календарь на текущий месяц
    now = datetime.now()
    cal_kb = _create_calendar(now.year, now.month)
    
    await callback.message.edit_text(
        "📅 Выберите дату доставки:",
        reply_markup=cal_kb
    )
    await callback.answer()

async def _ask_delivery_date_message(message: types.Message, state: FSMContext):
    """Показать календарь для выбора даты (для message)"""
    await state.set_state(Checkout.ASK_DATE)
    
    # Создаем календарь на текущий месяц
    now = datetime.now()
    cal_kb = _create_calendar(now.year, now.month)
    
    await message.answer(
        "📅 Выберите дату доставки:",
        reply_markup=cal_kb
    )

def _create_calendar(year: int, month: int):
    """Создать календарь на месяц"""
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    
    kb_rows = []
    
    # Заголовок месяца
    kb_rows.append([types.InlineKeyboardButton(
        text=f"{month_name} {year}",
        callback_data="ignore"
    )])
    
    # Дни недели
    kb_rows.append([
        types.InlineKeyboardButton(text="Пн", callback_data="ignore"),
        types.InlineKeyboardButton(text="Вт", callback_data="ignore"),
        types.InlineKeyboardButton(text="Ср", callback_data="ignore"),
        types.InlineKeyboardButton(text="Чт", callback_data="ignore"),
        types.InlineKeyboardButton(text="Пт", callback_data="ignore"),
        types.InlineKeyboardButton(text="Сб", callback_data="ignore"),
        types.InlineKeyboardButton(text="Вс", callback_data="ignore"),
    ])
    
    # Дни месяца
    today = datetime.now().date()
    for week in cal:
        week_row = []
        for day in week:
            if day == 0:
                week_row.append(types.InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_obj = datetime(year, month, day).date()
                if date_obj < today:
                    # Прошедшие дни
                    week_row.append(types.InlineKeyboardButton(text=" ", callback_data="ignore"))
                else:
                    # Доступные дни
                    week_row.append(types.InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"date_{year}_{month}_{day}"
                    ))
        kb_rows.append(week_row)
    
    # Навигация по месяцам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    kb_rows.append([
        types.InlineKeyboardButton(text="◀️", callback_data=f"cal_{prev_year}_{prev_month}"),
        types.InlineKeyboardButton(text="▶️", callback_data=f"cal_{next_year}_{next_month}")
    ])
    
    return types.InlineKeyboardMarkup(inline_keyboard=kb_rows)

@router.callback_query(F.data.startswith("cal_"))
async def change_calendar_month(callback: types.CallbackQuery, state: FSMContext):
    """Смена месяца в календаре"""
    _, year, month = callback.data.split("_")
    cal_kb = _create_calendar(int(year), int(month))
    
    await callback.message.edit_text(
        "📅 Выберите дату доставки:",
        reply_markup=cal_kb
    )
    await callback.answer()

@router.callback_query(F.data.startswith("date_"))
async def select_date(callback: types.CallbackQuery, state: FSMContext):
    """Выбор даты"""
    _, year, month, day = callback.data.split("_")
    selected_date = datetime(int(year), int(month), int(day)).date()
    
    await state.update_data(delivery_date=selected_date.isoformat())
    await state.set_state(Checkout.ASK_TIME)
    
    # Показываем выбор времени
    time_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🌅 09:00-12:00", callback_data="time_morning")],
        [types.InlineKeyboardButton(text="🌞 12:00-15:00", callback_data="time_day")],
        [types.InlineKeyboardButton(text="🌇 15:00-18:00", callback_data="time_evening")],
        [types.InlineKeyboardButton(text="🌃 18:00-21:00", callback_data="time_night")],
        [types.InlineKeyboardButton(text="🕐 Указать точное время", callback_data="time_exact")]
    ])
    
    date_str = selected_date.strftime("%d.%m.%Y")
    await callback.message.edit_text(
        f"✅ Дата: {date_str}\n\n🕐 Выберите время доставки:",
        reply_markup=time_kb
    )
    await callback.answer()

@router.callback_query(F.data.startswith("time_"))
async def select_time(callback: types.CallbackQuery, state: FSMContext):
    """Выбор времени"""
    time_periods = {
        "time_morning": "09:00-12:00",
        "time_day": "12:00-15:00", 
        "time_evening": "15:00-18:00",
        "time_night": "18:00-21:00"
    }
    
    if callback.data == "time_exact":
        await callback.message.edit_text(
            "🕐 Введите точное время доставки:\n\n"
            "Пример: 14:30"
        )
        await callback.answer()
        return
    
    time_slot = time_periods[callback.data]
    await state.update_data(delivery_time=time_slot)
    await _show_order_confirmation(callback, state)

@router.message(Checkout.ASK_TIME)
async def process_exact_time(message: types.Message, state: FSMContext):
    """Обработка точного времени"""
    time_text = message.text.strip()
    
    # Простая валидация формата времени
    try:
        datetime.strptime(time_text, "%H:%M")
        await state.update_data(delivery_time=time_text)
        await _show_order_confirmation_message(message, state)
    except ValueError:
        await message.answer("❌ Неверный формат времени. Пример: 14:30")

async def _show_order_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Показать подтверждение заказа"""
    await _show_confirmation_logic(callback.message, state, callback.from_user.id, is_callback=True)

async def _show_order_confirmation_message(message: types.Message, state: FSMContext):
    """Показать подтверждение заказа для message"""
    await _show_confirmation_logic(message, state, message.from_user.id, is_callback=False)

async def _show_confirmation_logic(message, state: FSMContext, user_id: int, is_callback: bool):
    """Общая логика показа подтверждения"""
    cart = get_cart(user_id)
    if not cart:
        text = "❌ Корзина пуста"
        if is_callback:
            await message.edit_text(text)
        else:
            await message.answer(text)
        await state.clear()
        return

    data = await state.get_data()
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, user_id)
        catalog_service = CatalogService(session)
        
        total = Decimal("0")
        lines = []
        
        for pid, qty in cart.items():
            try:
                product = await catalog_service.get_product(int(pid))
                price = Decimal(str(product.price))
                qty_d = Decimal(str(qty))
                line_total = price * qty_d
                total += line_total
                
                name = product.name_ru if lang == "ru" else product.name_uz
                lines.append(f"• {name} — {qty} × {price} сум")
                
            except ProductNotFoundError:
                continue

    if not lines:
        text = "❌ Корзина пуста"
        if is_callback:
            await message.edit_text(text)
        else:
            await message.answer(text)
        await state.clear()
        return

    # Формируем текст подтверждения
    delivery_date = data.get('delivery_date', 'не указана')
    delivery_time = data.get('delivery_time', 'не указано')
    
    text = (
        f"📋 <b>Подтверждение заказа</b>\n\n"
        f"🛍 <b>Товары:</b>\n" + "\n".join(lines) + 
        f"\n\n💰 <b>Итого: {total} сум</b>\n\n"
        f"📍 <b>Адрес:</b> {data['address']}\n"
        f"📞 <b>Телефон:</b> {data['phone']}\n"
        f"📅 <b>Дата:</b> {delivery_date}\n"
        f"🕐 <b>Время:</b> {delivery_time}"
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="confirm_ok")],
        [types.InlineKeyboardButton(text="❌ Отменить", callback_data="confirm_cancel")],
    ])
    
    await state.set_state(Checkout.CONFIRM)
    
    if is_callback:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(Checkout.CONFIRM, F.data == "confirm_ok")
async def create_order(callback: types.CallbackQuery, state: FSMContext):
    """Создание заказа"""
    cart = get_cart(callback.from_user.id)
    if not cart:
        async for session in get_session():
            user, lang = await _get_user_and_lang(session, callback.from_user.id)
        await callback.message.edit_text("❌ Корзина пуста")
        await state.clear()
        await callback.answer()
        return

    data = await state.get_data()

    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            await state.clear()
            await callback.answer()
            return

        try:
            # Создаем заказ через сервис
            order_service = OrderService(session)
            
            # Формируем комментарий
            delivery_date = data.get('delivery_date', '')
            delivery_time = data.get('delivery_time', '')
            comment = f"Доставка: {delivery_date} в {delivery_time}"
            
            if 'latitude' in data and 'longitude' in data:
                comment += f"\nКоординаты: {data['latitude']}, {data['longitude']}"
            
            order_data = OrderCreate(
                user_id=user.id,
                address=data["address"],
                phone=data["phone"],
                comment=comment
            )
            
            order = await order_service.create_order(
                user_id=user.id,
                cart_items=cart,
                order_data=order_data
            )
            
            await session.commit()
            
            # Очищаем корзину
            clear_cart(callback.from_user.id)
            
            # Уведомляем флористов и отправляем в канал
            await _notify_about_new_order(callback.bot, order, session, lang)
            
            await callback.message.edit_text(
                f"✅ <b>Заказ создан!</b>\n\n"
                f"🆔 Номер заказа: <b>#{order.id}</b>\n\n"
                f"Мы свяжемся с вами для уточнения деталей.",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]),
                parse_mode="HTML"
            )
            
        except Exception as e:
            await callback.message.edit_text(f"❌ Ошибка создания заказа: {str(e)}")
            
    await state.clear()
    await callback.answer()

async def _notify_about_new_order(bot, order, session, lang):
    """Уведомить флористов о новом заказе"""
    try:
        # СНАЧАЛА получаем заказ с полными данными (включая items)
        from app.services import OrderService
        order_service = OrderService(session)
        
        # Получаем заказ с загруженными связями
        full_order = await order_service.get_order_with_details(order.id)
        
        # Уведомляем в личные сообщения
        notification_service = NotificationService(bot)
        user_service = UserService(session)
        
        florists = await user_service.user_repo.get_by_role(RoleEnum.florist)
        owners = await user_service.user_repo.get_by_role(RoleEnum.owner)
        all_florists = florists + owners
        
        print(f"📧 Отправляем уведомления {len(all_florists)} флористам")
        
        if all_florists:
            await notification_service.notify_florists_about_order(all_florists, full_order, lang)
        
        # Отправляем в канал флористов
        from app.config import settings
        if settings.FLORIST_CHANNEL_ID:
            print(f"📢 Отправляем в канал {settings.FLORIST_CHANNEL_ID}")
            await _send_order_to_channel(bot, full_order, settings.FLORIST_CHANNEL_ID)
        else:
            print("⚠️ FLORIST_CHANNEL_ID не настроен")
            
    except Exception as e:
        print(f"❌ Notification error: {e}")
        import traceback
        traceback.print_exc()

async def _send_order_to_channel(bot, order, channel_id):
    """Отправить заказ в канал флористов С ПОДРОБНОСТЯМИ"""
    try:
        # Проверяем настройки канала
        if not channel_id:
            print("⚠️ FLORIST_CHANNEL_ID не настроен в .env")
            return
            
        if not channel_id.startswith("-"):
            print(f"⚠️ Неверный формат FLORIST_CHANNEL_ID: {channel_id}")
            return
        
        # Получаем детали заказа
        user_name = getattr(order.user, 'first_name', 'Неизвестно') or 'Неизвестно'
        phone = order.phone or 'Не указан'
        address = order.address or 'Не указан'
        comment = order.comment or 'Нет'
        
        # ПОЛУЧАЕМ СОСТАВ ЗАКАЗА - ИСПРАВЛЕННАЯ ЛОГИКА
        order_items = []
        try:
            if hasattr(order, 'items') and order.items:
                for item in order.items:
                    if hasattr(item, 'product') and item.product:
                        order_items.append(f"• {item.product.name_ru} × {item.qty}")
                    else:
                        order_items.append(f"• Товар ID:{item.product_id} × {item.qty}")
        except Exception as e:
            print(f"Error getting order items for channel: {e}")
        
        items_text = "\n".join(order_items) if order_items else "Состав недоступен"
        
        text = (
            f"🆕 <b>Новый заказ #{order.id}</b>\n\n"
            f"👤 <b>Клиент:</b> {user_name}\n"
            f"📞 <b>Телефон:</b> {phone}\n"
            f"📍 <b>Адрес:</b> {address}\n"
            f"💰 <b>Сумма:</b> {order.total_price} сум\n"
            f"🗓 <b>Создан:</b> {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🛍 <b>Состав:</b>\n{items_text}\n\n"
            f"💬 <b>Комментарий:</b> {comment}"
        )
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Принять в работу", callback_data=f"accept_order_{order.id}")],
            [types.InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_order_{order.id}")]
        ])
        
        await bot.send_message(
            chat_id=int(channel_id),
            text=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
        print(f"✅ Заказ #{order.id} отправлен в канал {channel_id}")
        
    except Exception as e:
        print(f"❌ Ошибка отправки в канал {channel_id}: {e}")
        import traceback
        traceback.print_exc()

@router.callback_query(Checkout.CONFIRM, F.data == "confirm_cancel")
async def cancel_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Отмена подтверждения заказа"""
    await state.clear()
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(
        "❌ Заказ отменен",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    """Игнорировать callback (для элементов календаря)"""
    await callback.answer()


@router.callback_query(F.data.startswith("accept_order_"))
async def florist_accept_order_from_channel(callback: types.CallbackQuery):
    """Флорист принимает заказ ИЗ КАНАЛА"""
    try:
        order_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат команды", show_alert=True)
        return
    
    async for session in get_session():
        from app.services import OrderService, NotificationService
        order_service = OrderService(session)
        
        # Получаем информацию о пользователе
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        try:
            # Получаем заказ
            order = await order_service.get_order_with_details(order_id)
            
            # Проверяем что заказ еще можно принять
            from app.models import OrderStatusEnum
            if order.status not in [OrderStatusEnum.new, OrderStatusEnum.await_florist]:
                await callback.answer("❌ Заказ уже обработан", show_alert=True)
                return
            
            # Обновляем статус заказа
            updated_order = await order_service.update_order_status(order_id, OrderStatusEnum.accepted)
            await session.commit()
            
            # Обновляем сообщение в канале
            user_name = f"{user.first_name} {user.last_name or ''}".strip()
            await callback.message.edit_text(
                callback.message.text + f"\n\n✅ <b>ПРИНЯТ</b>\n👤 Флорист: {user_name}\n🕐 {datetime.now().strftime('%d.%m %H:%M')}",
                parse_mode="HTML",
                reply_markup=None  # Убираем кнопки
            )
            
            # Уведомляем других флористов и владельцев
            notification_service = NotificationService(callback.bot)
            await notification_service.notify_order_status_change(order, "accepted", user, lang)
            await notification_service.hide_order_from_other_florists(order_id, user)
            
            await callback.answer("✅ Заказ принят в работу")
            
        except Exception as e:
            print(f"Accept order error: {e}")
            await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("cancel_order_") & F.message.chat.type.in_(["channel", "supergroup"]))
async def florist_cancel_order_from_channel(callback: types.CallbackQuery):
    """Флорист отменяет заказ ИЗ КАНАЛА"""
    try:
        order_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат команды", show_alert=True)
        return
    
    async for session in get_session():
        from app.services import OrderService, NotificationService
        order_service = OrderService(session)
        
        # Получаем информацию о пользователе
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        try:
            # Получаем заказ
            order = await order_service.get_order_with_details(order_id)
            
            # Проверяем права на отмену
            from app.models import OrderStatusEnum, RoleEnum
            if order.status in [OrderStatusEnum.delivered, OrderStatusEnum.canceled]:
                await callback.answer("❌ Заказ уже завершен", show_alert=True)
                return
            
            # Обновляем статус заказа
            updated_order = await order_service.update_order_status(order_id, OrderStatusEnum.canceled)
            await session.commit()
            
            # Обновляем сообщение в канале
            user_name = f"{user.first_name} {user.last_name or ''}".strip()
            role_text = "👑 Владелец" if user.role == RoleEnum.owner else "🌸 Флорист"
            
            await callback.message.edit_text(
                callback.message.text + f"\n\n❌ <b>ОТМЕНЕН</b>\n👤 {role_text}: {user_name}\n🕐 {datetime.now().strftime('%d.%m %H:%M')}",
                parse_mode="HTML",
                reply_markup=None  # Убираем кнопки
            )
            
            # Уведомляем других флористов и владельцев
            notification_service = NotificationService(callback.bot)
            await notification_service.notify_order_status_change(order, "canceled", user, lang)
            
            await callback.answer("❌ Заказ отменен")
            
        except Exception as e:
            print(f"Cancel order error: {e}")
            await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
