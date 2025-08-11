from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update
from app.database import get_session
from app.models import User, Settings, RoleRequest
from app.translate import t

router = Router()

# FSM состояния для регистрации
class Registration(StatesGroup):
    CHOOSE_LANG = State()
    CHOOSE_ROLE = State()
    REQUEST_REASON = State()

@router.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    # Проверяем пользователя
    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == str(message.from_user.id)))
        user = result.scalars().first()

        if user:
            # Пользователь уже зарегистрирован, показываем меню
            await show_main_menu(message, user.lang or "ru", user.role)
            return

    # Новый пользователь, выбор языка
    await state.set_state(Registration.CHOOSE_LANG)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [types.InlineKeyboardButton(text="🇺🇿 Oʻzbekcha", callback_data="lang_uz")]
    ])
    await message.answer(t("ru", "start_choose_lang") + "\n" + t("uz", "start_choose_lang"), reply_markup=kb)

@router.callback_query(Registration.CHOOSE_LANG, F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    
    # Сохраняем язык в состоянии
    await state.update_data(lang=lang)
    await state.set_state(Registration.CHOOSE_ROLE)
    
    # Показываем выбор роли
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t(lang, "role_client"), callback_data="role_client")],
        [types.InlineKeyboardButton(text=t(lang, "role_florist"), callback_data="role_florist")],
        [types.InlineKeyboardButton(text=t(lang, "role_owner"), callback_data="role_owner")]
    ])
    
    await callback.message.edit_text(t(lang, "registration_choose_role"), reply_markup=kb)

@router.callback_query(Registration.CHOOSE_ROLE, F.data.startswith("role_"))
async def choose_role(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]
    data = await state.get_data()
    lang = data.get("lang", "ru")
    
    if role == "client":
        # Сразу создаем клиента
        await create_user(callback.from_user.id, callback.from_user.first_name, lang, "client")
        await show_main_menu_callback(callback, lang, "client")
        await state.clear()
    else:
        # Проверяем настройки регистрации
        async for session in get_session():
            result = await session.execute(select(Settings))
            settings = result.scalars().first()
            
            is_open = False
            if settings:
                if role == "florist":
                    is_open = settings.florist_registration_open
                elif role == "owner": 
                    is_open = settings.owner_registration_open
            
            if not is_open:
                await callback.message.edit_text(t(lang, "registration_closed"))
                await state.clear()
                return
        
        # Запрашиваем причину
        await state.update_data(role=role)
        await state.set_state(Registration.REQUEST_REASON)
        await callback.message.edit_text(t(lang, "ask_role_reason"))

@router.message(Registration.REQUEST_REASON)
async def process_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    role = data.get("role")
    reason = message.text.strip()
    
    # Создаем заявку
    async for session in get_session():
        # Сначала создаем пользователя как клиента
        await create_user(message.from_user.id, message.from_user.first_name, lang, "client")
        
        # Потом создаем заявку на роль
        request = RoleRequest(
            user_tg_id=str(message.from_user.id),
            requested_role=role,
            reason=reason
        )
        session.add(request)
        await session.commit()
        
        # Уведомляем админов
        await notify_admins_about_request(message.bot, request, lang)
    
    await message.answer(t(lang, "role_request_sent"))
    await state.clear()

# Функция создания пользователя
async def create_user(tg_id: int, first_name: str, lang: str, role: str = "client"):
    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == str(tg_id)))
        user = result.scalars().first()
        
        if not user:
            user = User(
                tg_id=str(tg_id),
                first_name=first_name,
                lang=lang,
                role=role
            )
            session.add(user)
        else:
            user.lang = lang
            if role != "client":
                user.role = role
        
        await session.commit()

# Функция показа главного меню (для обычных сообщений)
async def show_main_menu(message: types.Message, lang: str, role: str = "client"):
    kb_rows = [
        [types.InlineKeyboardButton(text=t(lang, "menu_catalog"), callback_data="open_catalog")],
        [types.InlineKeyboardButton(text=t(lang, "menu_cart"), callback_data="open_cart")],
        [types.InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data="my_orders")]
    ]
    
    # Добавляем админские кнопки для владельца
    if role == "owner":
        kb_rows.extend([
            [types.InlineKeyboardButton(text=t(lang, "menu_analytics"), callback_data="analytics")],
            [types.InlineKeyboardButton(text=t(lang, "menu_manage_products"), callback_data="manage_products")],
            [types.InlineKeyboardButton(text=t(lang, "menu_registration_settings"), callback_data="registration_settings")]
        ])
    
    # Добавляем кнопки флориста
    if role in ["florist", "owner"]:
        kb_rows.append([types.InlineKeyboardButton(text=t(lang, "menu_manage_orders"), callback_data="manage_orders")])
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await message.answer(f"{t(lang, 'menu_title')}", reply_markup=kb)

# Функция показа главного меню (для callback)
async def show_main_menu_callback(callback: types.CallbackQuery, lang: str, role: str = "client"):
    kb_rows = [
        [types.InlineKeyboardButton(text=t(lang, "menu_catalog"), callback_data="open_catalog")],
        [types.InlineKeyboardButton(text=t(lang, "menu_cart"), callback_data="open_cart")],
        [types.InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data="my_orders")]
    ]
    
    # Добавляем админские кнопки для владельца
    if role == "owner":
        kb_rows.extend([
            [types.InlineKeyboardButton(text=t(lang, "menu_analytics"), callback_data="analytics")],
            [types.InlineKeyboardButton(text=t(lang, "menu_manage_products"), callback_data="manage_products")],
            [types.InlineKeyboardButton(text=t(lang, "menu_registration_settings"), callback_data="registration_settings")]
        ])
    
    # Добавляем кнопки флориста
    if role in ["florist", "owner"]:
        kb_rows.append([types.InlineKeyboardButton(text=t(lang, "menu_manage_orders"), callback_data="manage_orders")])
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text(f"{t(lang, 'menu_title')}", reply_markup=kb)

# Заглушки для нереализованных функций админа
@router.callback_query(F.data == "analytics")
async def analytics_placeholder(callback: types.CallbackQuery):
    await callback.message.edit_text("📊 Аналитика (в разработке)")
    await callback.answer()

@router.callback_query(F.data == "manage_products") 
async def manage_products_placeholder(callback: types.CallbackQuery):
    await callback.message.edit_text("📦 Управление товарами (в разработке)")
    await callback.answer()

@router.callback_query(F.data == "manage_orders")
async def manage_orders_placeholder(callback: types.CallbackQuery):
    await callback.message.edit_text("📋 Управление заказами (в разработке)")
    await callback.answer()

@router.callback_query(F.data == "registration_settings")
async def registration_settings_redirect(callback: types.CallbackQuery):
    # Перенаправляем к админ обработчику
    await callback.message.edit_text("⚙️ Переход к настройкам регистрации...")
    # Вызываем функцию из admin.py
    from app.handlers.admin import manage_registration_settings
    await manage_registration_settings(callback)

# Обработчик возврата в главное меню
@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery):
    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == str(callback.from_user.id)))
        user = result.scalars().first()
        
        if not user:
            await callback.message.edit_text("Пользователь не найден. Нажмите /start")
            return
        
        await show_main_menu_callback(callback, user.lang or "ru", user.role or "client")
        await callback.answer()
async def notify_admins_about_request(bot, request: RoleRequest, lang: str):
    """Уведомить админов о новой заявке на роль"""
    # Находим всех владельцев
    async for session in get_session():
        result = await session.execute(select(User).where(User.role == "owner"))
        owners = result.scalars().all()
        
        for owner in owners:
            try:
                text = (
                    f"🆕 Новая заявка на роль\n\n"
                    f"👤 Пользователь: {request.user_tg_id}\n"
                    f"🎯 Роль: {request.requested_role}\n"
                    f"📝 Причина: {request.reason}\n"
                )
                
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{request.id}")],
                    [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{request.id}")]
                ])
                
                await bot.send_message(chat_id=int(owner.tg_id), text=text, reply_markup=kb)
            except Exception as e:
                print(f"Не удалось отправить уведомление админу {owner.tg_id}: {e}")