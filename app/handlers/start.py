from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.repositories import SettingsRepository
from app.services import NotificationService
from app.models import RequestedRoleEnum, RoleRequest
from app.translate import t

router = Router()

# FSM состояния для регистрации
class Registration(StatesGroup):
    CHOOSE_LANG = State()
    CHOOSE_ROLE = State()
    REQUEST_REASON = State()

@router.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext, user=None, session=None):
    """Команда /start - проверка пользователя или регистрация"""
    # Пользователь автоматически создан через AuthMiddleware
    if user and user.lang:
        # Пользователь уже зарегистрирован, показываем меню
        await _show_main_menu(message, user.lang, user.role.value)
        return

    # Новый пользователь без языка, начинаем регистрацию
    await state.set_state(Registration.CHOOSE_LANG)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [types.InlineKeyboardButton(text="🇺🇿 Oʻzbekcha", callback_data="lang_uz")]
    ])
    await message.answer(
        t("ru", "start_choose_lang") + "\n" + t("uz", "start_choose_lang"), 
        reply_markup=kb
    )

@router.callback_query(Registration.CHOOSE_LANG, F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery, state: FSMContext, user=None, session=None):
    """Выбор языка"""
    lang = callback.data.split("_")[1]
    
    await state.update_data(lang=lang)
    await state.set_state(Registration.CHOOSE_ROLE)
    
    # Обновляем язык пользователя
    if user and session:
        user.lang = lang
        await session.commit()
    
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
async def choose_role(callback: types.CallbackQuery, state: FSMContext, user=None, user_service=None, session=None):
    """Выбор роли"""
    role = callback.data.split("_")[1]
    data = await state.get_data()
    lang = data.get("lang", "ru")
    
    if role == "client":
        # Пользователь уже создан как client через middleware
        await _show_main_menu_callback(callback, lang, "client")
        await state.clear()
        
    else:
        # Проверяем возможность регистрации для роли
        if user_service:
            is_open = await user_service.check_role_registration_open(role)
        else:
            is_open = False
        
        if not is_open:
            await callback.message.edit_text(t(lang, "registration_closed"))
            await state.clear()
            return
        
        # Запрашиваем причину
        await state.update_data(role=role)
        await state.set_state(Registration.REQUEST_REASON)
        await callback.message.edit_text(t(lang, "ask_role_reason"))

@router.message(Registration.REQUEST_REASON)
async def process_reason(message: types.Message, state: FSMContext, user=None, user_service=None, session=None):
    """Обработка причины для заявки на роль"""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    role = data.get("role")
    reason = message.text.strip()
    
    if not user or not session:
        await message.answer("Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Создаем заявку на роль
    role_enum = RequestedRoleEnum.florist if role == "florist" else RequestedRoleEnum.owner
    request = RoleRequest(
        user_id=user.id,
        requested_role=role_enum,
        reason=reason
    )
    session.add(request)
    await session.flush()
    
    # Уведомляем админов
    if user_service:
        notification_service = NotificationService(message.bot)
        admins = await user_service.get_admins()
        await notification_service.notify_admins_about_role_request(admins, request)
    
    await session.commit()
    await message.answer(t(lang, "role_request_sent"))
    await state.clear()

# Вспомогательные функции (упрощены благодаря middleware)
async def _show_main_menu(message: types.Message, lang: str, role: str = "client"):
    """Показать главное меню"""
    kb = await _create_main_menu_keyboard(lang, role)
    await message.answer(t(lang, 'menu_title'), reply_markup=kb)

async def _show_main_menu_callback(callback: types.CallbackQuery, lang: str, role: str = "client"):
    """Показать главное меню для callback"""
    kb = await _create_main_menu_keyboard(lang, role)
    await callback.message.edit_text(t(lang, 'menu_title'), reply_markup=kb)

async def _create_main_menu_keyboard(lang: str, role: str) -> types.InlineKeyboardMarkup:
    """Создать клавиатуру главного меню"""
    kb_rows = [
        [types.InlineKeyboardButton(text=t(lang, "menu_catalog"), callback_data="open_catalog")],
        [types.InlineKeyboardButton(text=t(lang, "menu_cart"), callback_data="open_cart")],
        [types.InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data="my_orders")]
    ]
    
    if role == "owner":
        kb_rows.extend([
            [types.InlineKeyboardButton(text=t(lang, "menu_analytics"), callback_data="analytics")],
            [types.InlineKeyboardButton(text=t(lang, "menu_manage_products"), callback_data="manage_products")],
            [types.InlineKeyboardButton(text=t(lang, "menu_registration_settings"), callback_data="manage_registration")]
        ])
    
    if role in ["florist", "owner"]:
        kb_rows.append([types.InlineKeyboardButton(text=t(lang, "menu_manage_orders"), callback_data="florist_orders")])
    
    return types.InlineKeyboardMarkup(inline_keyboard=kb_rows)

# Заглушки
@router.callback_query(F.data == "analytics")
async def analytics_placeholder(callback: types.CallbackQuery):
    await callback.message.edit_text("📊 Аналитика (в разработке)")

@router.callback_query(F.data == "manage_products") 
async def manage_products_placeholder(callback: types.CallbackQuery):
    await callback.message.edit_text("📦 Управление товарами (в разработке)")

@router.callback_query(F.data == "manage_orders")
async def manage_orders_placeholder(callback: types.CallbackQuery):
    await callback.message.edit_text("📋 Управление заказами (в разработке)")

# Обработчик возврата в главное меню (упрощен)
@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery, user=None):
    """Возврат в главное меню"""
    if user:
        await _show_main_menu_callback(callback, user.lang or "ru", user.role.value)
        await callback.answer()
    else:
        await callback.message.edit_text("Пользователь не найден. Нажмите /start")