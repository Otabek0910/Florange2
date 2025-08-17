from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.repositories import SettingsRepository
from app.services import NotificationService
from app.models import RequestedRoleEnum, RoleRequest, RoleEnum, User
from app.translate import t
from app.utils.validators import validate_phone
from datetime import datetime

router = Router()

# FSM состояния для регистрации (БЕЗ REQUEST_REASON)
class Registration(StatesGroup):
    CHOOSE_LANG = State()
    CHOOSE_ROLE = State()
    ASK_NAME = State()
    ASK_PHONE = State()

@router.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext, user=None, tg_user=None):
    """Команда /start - проверка пользователя или регистрация"""
    
    if user and user.lang:
        # Пользователь уже зарегистрирован, показываем меню
        await _show_main_menu(message, user.lang, user.role.value)
        return

    # НОВЫЙ пользователь - запускаем регистрацию
    await state.clear()
    await state.set_state(Registration.CHOOSE_LANG)
    
    # Сохраняем Telegram данные в FSM
    await state.update_data(
        tg_id=str(tg_user.id),
        first_name=tg_user.first_name or ""
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [types.InlineKeyboardButton(text="🇺🇿 Oʻzbekcha", callback_data="lang_uz")]
    ])
    await message.answer(
        t("ru", "start_choose_lang") + "\n" + t("uz", "start_choose_lang"), 
        reply_markup=kb
    )

@router.callback_query(Registration.CHOOSE_LANG, F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery, state: FSMContext, session=None):
    """Выбор языка"""
    lang = callback.data.split("_")[1]
    await state.update_data(lang=lang)
    await state.set_state(Registration.CHOOSE_ROLE)
    
    # Проверяем настройки регистрации
    if session:
        settings_repo = SettingsRepository(session)
        florist_open = await settings_repo.get_bool_value("florist_registration_open", False)
        owner_open = await settings_repo.get_bool_value("owner_registration_open", False)
    else:
        florist_open = owner_open = False
    
    # Формируем кнопки
    buttons = [[types.InlineKeyboardButton(text=t(lang, "role_client"), callback_data="role_client")]]
    
    if florist_open:
        buttons.append([types.InlineKeyboardButton(text=t(lang, "role_florist"), callback_data="role_florist")])
    
    if owner_open:
        buttons.append([types.InlineKeyboardButton(text=t(lang, "role_owner"), callback_data="role_owner")])
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(t(lang, "registration_choose_role"), reply_markup=kb)

@router.callback_query(Registration.CHOOSE_ROLE, F.data.startswith("role_"))
async def choose_role(callback: types.CallbackQuery, state: FSMContext):
    """Выбор роли и переход к имени"""
    role = callback.data.split("_")[1]
    data = await state.get_data()
    lang = data.get("lang", "ru")
    
    await state.update_data(role=role)
    await state.set_state(Registration.ASK_NAME)
    
    # Удаляем предыдущее сообщение и отправляем новое
    await callback.message.delete()
    await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text=t(lang, "ask_full_name")
    )

@router.message(Registration.ASK_NAME)
async def process_name(message: types.Message, state: FSMContext):
    """Обработка имени и фамилии"""
    name = message.text.strip()
    data = await state.get_data()
    lang = data.get("lang", "ru")
    
    # Проверяем что введено минимум имя
    if len(name) < 2:
        await message.answer(t(lang, "invalid_name"))
        return
    
    await state.update_data(full_name=name)
    await state.set_state(Registration.ASK_PHONE)
    
    # Удаляем сообщение пользователя
    await message.delete()
    
    # Создаем гибридную клавиатуру для телефона
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=t(lang, "share_phone_button"), request_contact=True)],
            [types.KeyboardButton(text=t(lang, "enter_manually_button"))]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(t(lang, "ask_phone_registration"), reply_markup=kb)

@router.message(Registration.ASK_PHONE, F.contact)
async def process_contact(message: types.Message, state: FSMContext, session=None):
    """Обработка контакта от кнопки"""
    phone = message.contact.phone_number
    data = await state.get_data()
    
    await _complete_registration(message, state, session, phone, data)

@router.message(Registration.ASK_PHONE, F.text)
async def process_phone_text(message: types.Message, state: FSMContext, session=None):
    """Обработка телефона текстом"""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    
    if message.text == t(lang, "enter_manually_button"):
        await message.answer(t(lang, "enter_phone_manually"))
        return
    
    phone = message.text.strip()
    
    if not validate_phone(phone):
        await message.answer(t(lang, "invalid_phone"))
        return
    
    await _complete_registration(message, state, session, phone, data)

async def _complete_registration(message, state: FSMContext, session, phone: str, data: dict):
    """Завершение регистрации"""
    lang = data.get("lang", "ru")
    role = data.get("role", "client")
    full_name = data.get("full_name", "")
    tg_id = data.get("tg_id")
    
    # Разбиваем имя
    name_parts = full_name.split(" ", 1)
    first_name = name_parts[0] if name_parts else "Пользователь"
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    try:
        if role == "client":
            # Создаем клиента сразу
            from app.repositories import UserRepository
            user_repo = UserRepository(session)
            
            new_user = User(
                tg_id=tg_id,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                lang=lang,
                role=RoleEnum.client
            )
            
            await user_repo.create(new_user)
            await session.commit()
            
            # АГРЕССИВНАЯ ОЧИСТКА для клиентов
            await _aggressive_chat_cleanup(message, 20)
            
            # Финальное сообщение и меню
            welcome_msg = await message.answer(
                t(lang, "registration_complete"),
                reply_markup=types.ReplyKeyboardRemove()
            )
            await _show_main_menu(message, lang, "client")
            
            # Удаляем welcome сообщение через 3 секунды
            import asyncio
            asyncio.create_task(_delete_message_later(message.bot, message.chat.id, welcome_msg.message_id, 3))
            
        else:
            # Создаем заявку для флориста/владельца БЕЗ user_data поля
            request_role = RequestedRoleEnum.florist if role == "florist" else RequestedRoleEnum.owner
            
            new_request = RoleRequest(
                user_tg_id=tg_id,
                requested_role=request_role,
                reason="Автоматическая заявка",
                first_name=first_name,      # ИСПОЛЬЗУЕМ ОТДЕЛЬНЫЕ ПОЛЯ
                last_name=last_name,        # ВМЕСТО user_data
                phone=phone,
                lang=lang
                # БЕЗ user_data=... - это поле не существует!
            )
            
            session.add(new_request)
            await session.commit()
            
            # Уведомляем админов
            from app.services import NotificationService, UserService
            notification_service = NotificationService(message.bot)
            user_service = UserService(session)
            
            admins = await user_service.user_repo.get_by_role(RoleEnum.owner)
            if admins:
                await notification_service.notify_admins_about_role_request(admins, new_request)
            
            # АГРЕССИВНАЯ ОЧИСТКА для флористов
            await _aggressive_chat_cleanup(message, 20)
            
            # Финальное сообщение
            final_msg = await message.answer(
                f"✅ Заявка на роль отправлена администратору!\n\nВ течение суток с вами свяжутся.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            # Удаляем финальное сообщение через 5 секунд
            import asyncio
            asyncio.create_task(_delete_message_later(message.bot, message.chat.id, final_msg.message_id, 5))
        
    except Exception as e:
        print(f"Registration error: {e}")
        await message.answer(f"❌ Ошибка регистрации: {str(e)}")
    
    await state.clear()

async def _aggressive_chat_cleanup(message, count: int = 20):
    """Агрессивная очистка чата"""
    try:
        # Удаляем сообщения в обратном порядке
        for i in range(count):
            try:
                await message.bot.delete_message(message.chat.id, message.message_id - i)
            except Exception:
                continue
    except Exception as e:
        print(f"Chat cleanup error: {e}")

async def _delete_message_later(bot, chat_id: int, message_id: int, delay: int):
    """Удалить сообщение через delay секунд"""
    import asyncio
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass

# Вспомогательные функции
async def _show_main_menu(message: types.Message, lang: str, role: str = "client"):
    """Показать главное меню"""
    kb = await _create_main_menu_keyboard(message.bot, lang, role)
    await message.answer(t(lang, 'menu_title'), reply_markup=kb)

async def _create_main_menu_keyboard(bot, lang: str, role: str) -> types.InlineKeyboardMarkup:
    """Создать клавиатуру главного меню ПО РОЛЯМ"""
    
    kb_rows = []
    
    if role == "client":
        # МЕНЮ КЛИЕНТА
        kb_rows = [
            [types.InlineKeyboardButton(text=t(lang, "menu_catalog"), callback_data="open_catalog")],
            [types.InlineKeyboardButton(text=t(lang, "menu_cart"), callback_data="open_cart")],
            [types.InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data="my_orders")],
            [types.InlineKeyboardButton(text=t(lang, "menu_consultation"), callback_data="consultation_start")],
            [types.InlineKeyboardButton(text=t(lang, "history_consultations"), callback_data="consultation_history")]
        ]
    
    elif role == "florist":
        # МЕНЮ ФЛОРИСТА
        kb_rows = [
            [types.InlineKeyboardButton(text="📋 Управление заказами", callback_data="manage_orders")],
            [types.InlineKeyboardButton(text="💬 Консультации", callback_data="florist_consultations")],
            [types.InlineKeyboardButton(text="📊 Мои статистика", callback_data="my_stats")],
            [types.InlineKeyboardButton(text="📦 Склад", callback_data="warehouse_status")],
            [types.InlineKeyboardButton(text="👤 Мой профиль", callback_data="my_profile")]
        ]
    
    elif role == "owner":
        # МЕНЮ ВЛАДЕЛЬЦА
        pending_count = await _get_pending_requests_count(bot)
        requests_text = "📋 Заявки на роли"
        if pending_count > 0:
            requests_text += f" ({pending_count})"
        
        kb_rows = [
            [types.InlineKeyboardButton(text="📊 Аналитика", callback_data="analytics")],
            [types.InlineKeyboardButton(text="📋 Управление заказами", callback_data="manage_orders")],
            [types.InlineKeyboardButton(text="👥 Управление персоналом", callback_data="manage_florists")],
            [types.InlineKeyboardButton(text="📦 Управление товарами", callback_data="manage_products")],
            [types.InlineKeyboardButton(text="📦 Склад и поставки", callback_data="warehouse_management")],
            [types.InlineKeyboardButton(text=requests_text, callback_data="manage_registration")],
            [types.InlineKeyboardButton(text="⚙️ Настройки системы", callback_data="system_settings")]
        ]
    
    # Кнопка смены языка для всех
    kb_rows.append([types.InlineKeyboardButton(text=f"🌍 {lang.upper()}", callback_data="change_language")])
    
    return types.InlineKeyboardMarkup(inline_keyboard=kb_rows)

# ДОБАВИТЬ заглушки для новых кнопок флориста в app/handlers/start.py:

@router.callback_query(F.data == "florist_consultations")
async def florist_consultations_placeholder(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text("💬 Управление консультациями (в разработке)", reply_markup=kb)

@router.callback_query(F.data == "my_stats")
async def my_stats_placeholder(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text("📊 Моя статистика (в разработке)", reply_markup=kb)

@router.callback_query(F.data == "warehouse_status")
async def warehouse_status_placeholder(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text("📦 Статус склада (в разработке)", reply_markup=kb)

@router.callback_query(F.data == "my_profile")
async def my_profile_placeholder(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text("👤 Мой профиль флориста (в разработке)", reply_markup=kb)

@router.callback_query(F.data == "warehouse_management")
async def warehouse_management_placeholder(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text("📦 Управление складом (в разработке)", reply_markup=kb)

@router.callback_query(F.data == "system_settings")
async def system_settings_placeholder(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text("⚙️ Настройки системы (в разработке)", reply_markup=kb)

async def _get_pending_requests_count(bot) -> int:
    """Получить количество ожидающих заявок"""
    try:
        from app.database.database import get_session
        from app.services import UserService
        from sqlalchemy import select, func
        from app.models import RoleRequest, RequestStatusEnum
        
        async for session in get_session():
            result = await session.execute(
                select(func.count(RoleRequest.id))
                .where(RoleRequest.status == RequestStatusEnum.pending)
            )
            return result.scalar() or 0
    except:
        return 0

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery, user=None):
    """Возврат в главное меню"""
    if user:
        kb = await _create_main_menu_keyboard(callback.bot, user.lang or "ru", user.role.value)
        await callback.message.edit_text(t(user.lang or "ru", 'menu_title'), reply_markup=kb)
        await callback.answer()
    else:
        await callback.message.edit_text("Пользователь не найден. Нажмите /start")

@router.callback_query(F.data == "change_language")
async def change_language_handler(callback: types.CallbackQuery, user=None):
    """Смена языка"""
    if not user:
        await callback.answer("Пользователь не найден")
        return
    
    # Показываем клавиатуру выбора языка
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🇷🇺 Русский"), types.KeyboardButton(text="🇺🇿 O'zbekcha")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.answer(t(user.lang or "ru", "choose_language"), reply_markup=kb)
    await callback.answer()

@router.message(F.text.in_(["🇷🇺 Русский", "🇺🇿 O'zbekcha"]))
async def process_language_change(message: types.Message, user=None, session=None):
    """Обработка смены языка"""
    if not user or not session:
        return
    
    new_lang = "ru" if "Русский" in message.text else "uz"
    
    # Обновляем язык в БД
    user.lang = new_lang
    await session.commit()
    
    # Убираем клавиатуру и показываем обновленное меню
    await message.answer("✅", reply_markup=types.ReplyKeyboardRemove())
    await _show_main_menu(message, new_lang, user.role.value)

# Заглушки (временно)
@router.callback_query(F.data == "analytics")
async def analytics_placeholder(callback: types.CallbackQuery, user=None):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text("📊 Аналитика (в разработке)", reply_markup=kb)

@router.callback_query(F.data == "manage_products") 
async def manage_products_placeholder(callback: types.CallbackQuery, user=None):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text("📦 Управление товарами (в разработке)", reply_markup=kb)

@router.callback_query(F.data == "main_menu")
async def show_main_menu_callback(callback: types.CallbackQuery, user=None):
    """Показать главное меню через callback"""
    if not user:
        await callback.answer("Пользователь не найден")
        return
    
    kb = await _create_main_menu_keyboard(callback.bot, user.lang, user.role.value)
    await callback.message.edit_text(t(user.lang, 'menu_title'), reply_markup=kb)