from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.repositories import SettingsRepository
from app.services import NotificationService
from app.models import RequestedRoleEnum, RoleRequest, RoleEnum, User
from app.translate import t
from app.utils.validators import validate_phone

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
async def process_contact_phone(message: types.Message, state: FSMContext, user_service=None, session=None):
    """Обработка телефона через кнопку"""
    phone = message.contact.phone_number
    
    # Удаляем сообщение с контактом
    await message.delete()
    
    await _complete_phone_registration(message, state, phone, user_service, session)

@router.message(Registration.ASK_PHONE, F.text)
async def process_manual_phone(message: types.Message, state: FSMContext, user_service=None, session=None):
    """Обработка ручного ввода телефона"""
    # Пропускаем кнопку "Ввести вручную"
    if message.text in [t("ru", "enter_manually_button"), t("uz", "enter_manually_button")]:
        data = await state.get_data()
        lang = data.get("lang", "ru")
        
        await message.delete()
        await message.answer(
            t(lang, "enter_phone_manually"), 
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    phone = message.text.strip()
    data = await state.get_data()
    lang = data.get("lang", "ru")
    
    # Валидация телефона
    if not validate_phone(phone):
        await message.delete()
        await message.answer(t(lang, "invalid_phone"))
        return
    
    # Удаляем сообщение пользователя
    await message.delete()
    
    await _complete_phone_registration(message, state, phone, user_service, session)

async def _complete_phone_registration(message: types.Message, state: FSMContext, phone: str, 
                                     user_service=None, session=None):
    """Завершение регистрации с телефоном"""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    role = data.get("role", "client")
    full_name = data.get("full_name", data.get("first_name", ""))
    
    await state.update_data(phone=phone)
    
    # Убираем клавиатуру
    try:
        temp_msg = await message.answer("...", reply_markup=types.ReplyKeyboardRemove())
        await temp_msg.delete()
    except:
        pass
    
    # Разделяем имя
    name_parts = full_name.split(maxsplit=1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    if role == "client":
        # Создаем клиента сразу
        if user_service and session:
            new_user = User(
                tg_id=data["tg_id"],
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                lang=lang,
                role=RoleEnum.client
            )
            
            await user_service.user_repo.create(new_user)
            await session.commit()
        
        # АГРЕССИВНАЯ ОЧИСТКА для клиентов
        await _aggressive_chat_cleanup(message, 20)
        
        # Финальное сообщение и меню
        welcome_msg = await message.answer(t(lang, "registration_complete"))
        await _show_main_menu(message, lang, "client")
        
        # Удаляем welcome сообщение через 3 секунды
        import asyncio
        asyncio.create_task(_delete_message_later(message.bot, message.chat.id, welcome_msg.message_id, 3))
        
        await state.clear()
        
    else:
        # Для флористов/владельцев создаем заявку БЕЗ запроса причины
        if not session:
            await message.answer("Ошибка: сессия не найдена")
            await state.clear()
            return
        
        # Сохраняем данные для создания после одобрения
        user_data = {
            "tg_id": data["tg_id"],
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "lang": lang,
            "requested_role": role
        }
        
        # Создаем заявку БЕЗ причины
        role_enum = RequestedRoleEnum.florist if role == "florist" else RequestedRoleEnum.owner
        request = RoleRequest(
            user_tg_id=data["tg_id"],
            requested_role=role_enum,
            reason="Автоматическая заявка",
            user_data=str(user_data)
        )
        session.add(request)
        await session.flush()
        
        # Уведомляем админов
        if user_service:
            notification_service = NotificationService(message.bot)
            admins = await user_service.get_admins()
            await notification_service.notify_admins_about_role_request(admins, request)
        
        await session.commit()
        
        # АГРЕССИВНАЯ ОЧИСТКА для флористов
        await _aggressive_chat_cleanup(message, 20)
        
        # Финальное сообщение
        final_msg = await message.answer(t(lang, "role_request_sent"))
        
        # Удаляем финальное сообщение через 5 секунд
        import asyncio
        asyncio.create_task(_delete_message_later(message.bot, message.chat.id, final_msg.message_id, 5))
        
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
    """Создать клавиатуру главного меню"""
    
    # Базовые кнопки для всех
    kb_rows = [
        [types.InlineKeyboardButton(text=t(lang, "menu_catalog"), callback_data="open_catalog")],
        [types.InlineKeyboardButton(text=t(lang, "menu_cart"), callback_data="open_cart")]
    ]
    
# 🆕 Добавляем консультацию ТОЛЬКО для клиентов
    if role == "client":
        kb_rows.append([types.InlineKeyboardButton(text=t(lang, "menu_consultation"), callback_data="consultation_start")])
        kb_rows.append([types.InlineKeyboardButton(text=t(lang, "history_consultations"), callback_data="consultation_history")])
    
    # Мои заказы для всех
    kb_rows.append([types.InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data="my_orders")])
    
    # Админские кнопки для владельца
    if role == "owner":
        # Получаем количество ожидающих заявок
        pending_count = await _get_pending_requests_count(bot)
        requests_text = t(lang, "menu_pending_requests")
        if pending_count > 0:
            requests_text += f" ({pending_count})"
        
        kb_rows.extend([
            [types.InlineKeyboardButton(text=t(lang, "menu_analytics"), callback_data="analytics")],
            [types.InlineKeyboardButton(text=t(lang, "menu_manage_products"), callback_data="manage_products")],
            [types.InlineKeyboardButton(text=requests_text, callback_data="manage_registration")]
        ])
    
    # Кнопки флориста и владельца
    if role in ["florist", "owner"]:
        kb_rows.append([types.InlineKeyboardButton(text=t(lang, "menu_manage_orders"), callback_data="florist_orders")])
    
    # Добавляем кнопку смены языка
    kb_rows.append([types.InlineKeyboardButton(text=f"🌍 {lang.upper()}", callback_data="change_language")])
    
    return types.InlineKeyboardMarkup(inline_keyboard=kb_rows)

async def _get_pending_requests_count(bot) -> int:
    """Получить количество ожидающих заявок"""
    try:
        from app.database import get_session
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
async def analytics_placeholder(callback: types.CallbackQuery):
    await callback.message.edit_text("📊 Аналитика (в разработке)")

@router.callback_query(F.data == "manage_products") 
async def manage_products_placeholder(callback: types.CallbackQuery):
    await callback.message.edit_text("📦 Управление товарами (в разработке)")

# Функция для показа меню пользователю (используется в admin.py)
async def _show_main_menu_to_user(bot, chat_id: int, lang: str, role: str):
    """Показать главное меню пользователю"""
    kb = await _create_main_menu_keyboard(bot, lang, role)
    await bot.send_message(
        chat_id=chat_id,
        text=t(lang, 'menu_title'),
        reply_markup=kb
    )