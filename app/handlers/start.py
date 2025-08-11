from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update
from app.database import get_session
from app.models import User, RoleEnum
from app.translate import t

router = Router()

class Registration(StatesGroup):
    CHOOSE_LANG = State()
    CHOOSE_ROLE = State()

@router.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    # Проверяем, зарегистрирован ли пользователь
    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == str(message.from_user.id)))
        user = result.scalars().first()

        if user and user.lang and user.role:
            # Пользователь полностью зарегистрирован - показать главное меню
            await show_main_menu(message, user.lang, user.role)
            return

    # Начинаем регистрацию
    await state.clear()
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
async def set_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(lang=lang)
    await state.set_state(Registration.CHOOSE_ROLE)

    # Проверяем, какие роли доступны для регистрации
    async for session in get_session():
        from app.models import Settings
        
        florist_open_result = await session.execute(
            select(Settings).where(Settings.key == "florist_registration_open")
        )
        owner_open_result = await session.execute(
            select(Settings).where(Settings.key == "owner_registration_open")
        )
        
        florist_open = florist_open_result.scalars().first()
        owner_open = owner_open_result.scalars().first()
        
        is_florist_open = florist_open and florist_open.value == "true"
        is_owner_open = owner_open and owner_open.value == "true"

    # Формируем кнопки в зависимости от доступности ролей
    buttons = [[types.InlineKeyboardButton(text=t(lang, "role_client"), callback_data="role_client")]]
    
    if is_florist_open:
        buttons.append([types.InlineKeyboardButton(text=t(lang, "role_florist"), callback_data="role_florist")])
    
    if is_owner_open:
        buttons.append([types.InlineKeyboardButton(text=t(lang, "role_owner"), callback_data="role_owner")])

    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Сообщение в зависимости от доступности ролей
    if not is_florist_open and not is_owner_open:
        text = t(lang, "choose_role_client_only")
    else:
        text = t(lang, "choose_role")
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(Registration.CHOOSE_ROLE, F.data.startswith("role_"))
async def set_role(callback: types.CallbackQuery, state: FSMContext):
    role_str = callback.data.split("_")[1]
    data = await state.get_data()
    lang = data["lang"]

    if role_str == "client":
        # Клиенты регистрируются сразу
        async for session in get_session():
            result = await session.execute(select(User).where(User.tg_id == str(callback.from_user.id)))
            user = result.scalars().first()

            if user:
                await session.execute(
                    update(User)
                    .where(User.tg_id == str(callback.from_user.id))
                    .values(lang=lang, role=RoleEnum.client)
                )
            else:
                user = User(
                    tg_id=str(callback.from_user.id),
                    first_name=callback.from_user.first_name,
                    lang=lang,
                    role=RoleEnum.client
                )
                session.add(user)
            
            await session.commit()

        await state.clear()
        await callback.message.edit_text(
            t(lang, "registration_complete", role=t(lang, "role_client"))
        )
        await show_main_menu(callback.message, lang, RoleEnum.client)
        
    else:
        # Флористы и владельцы подают заявку
        await state.update_data(requested_role=role_str)
        await state.set_state(Registration.REQUEST_REASON)
        
        await callback.message.edit_text(
            t(lang, "request_role_reason", role=t(lang, f"role_{role_str}"))
        )
    
    await callback.answer()

# Новое состояние для ввода причины заявки
class Registration(StatesGroup):
    CHOOSE_LANG = State()
    CHOOSE_ROLE = State()
    REQUEST_REASON = State()

@router.message(Registration.REQUEST_REASON)
async def submit_role_request(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    role_str = data["requested_role"]
    reason = message.text.strip()

    # Создаем заявку
    async for session in get_session():
        from app.models import RoleRequest, RequestedRoleEnum, Settings
        
        # Создаем или обновляем пользователя как клиента
        result = await session.execute(select(User).where(User.tg_id == str(message.from_user.id)))
        user = result.scalars().first()

        if user:
            await session.execute(
                update(User)
                .where(User.tg_id == str(message.from_user.id))
                .values(lang=lang, role=RoleEnum.client)  # Временно клиент
            )
        else:
            user = User(
                tg_id=str(message.from_user.id),
                first_name=message.from_user.first_name,
                lang=lang,
                role=RoleEnum.client
            )
            session.add(user)
            await session.flush()

        # Создаем заявку на роль
        role_enum = RequestedRoleEnum.florist if role_str == "florist" else RequestedRoleEnum.owner
        request = RoleRequest(
            user_id=user.id,
            requested_role=role_enum,
            reason=reason
        )
        session.add(request)
        await session.commit()

        # Уведомляем администраторов
        await notify_admins_about_request(message.bot, request, user, lang)

    await state.clear()
    await message.answer(
        t(lang, "role_request_submitted", role=t(lang, f"role_{role_str}"))
    )
    await show_main_menu(message, lang, RoleEnum.client)

async def notify_admins_about_request(bot, request: 'RoleRequest', user: User, lang: str):
    """Уведомить админов о новой заявке на роль"""
    async for session in get_session():
        # Ищем владельцев (они могут подтверждать флористов)
        if request.requested_role == RequestedRoleEnum.florist:
            admin_query = select(User).where(User.role.in_([RoleEnum.owner]))
        else:  # owner requests need super admin confirmation
            # Для владельцев нужен супер-админ (можно хранить в настройках)
            admin_query = select(User).where(User.role == RoleEnum.owner)
            
        admins_result = await session.execute(admin_query)
        admins = admins_result.scalars().all()

        role_text = "флориста" if request.requested_role == RequestedRoleEnum.florist else "владельца"
        
        for admin in admins:
            try:
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_req_{request.id}")],
                    [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_req_{request.id}")],
                    [types.InlineKeyboardButton(text="👤 Профиль", callback_data=f"profile_req_{request.id}")]
                ])
                
                text = (
                    f"🆕 Новая заявка на роль {role_text}\n\n"
                    f"👤 {user.first_name} (@{user.tg_id})\n"
                    f"💬 Причина: {request.reason}\n"
                    f"📅 {request.created_at.strftime('%d.%m.%Y %H:%M')}"
                )
                
                await bot.send_message(
                    chat_id=int(admin.tg_id),
                    text=text,
                    reply_markup=kb
                )
            except Exception as e:
                print(f"Не удалось уведомить админа {admin.tg_id}: {e}")

async def show_main_menu(message: types.Message, lang: str, role: RoleEnum):
    """Показать главное меню в зависимости от роли"""
    
    if role == RoleEnum.client:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t(lang, "menu_catalog"), callback_data="open_catalog")],
            [types.InlineKeyboardButton(text=t(lang, "menu_cart"), callback_data="open_cart")],
            [types.InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data="my_orders")]
        ])
    elif role == RoleEnum.florist:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data="florist_orders")],
            [types.InlineKeyboardButton(text=t(lang, "menu_inventory"), callback_data="manage_inventory")]
        ])
    elif role == RoleEnum.owner:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t(lang, "menu_catalog"), callback_data="open_catalog")],
            [types.InlineKeyboardButton(text=t(lang, "menu_analytics"), callback_data="view_analytics")],
            [types.InlineKeyboardButton(text=t(lang, "menu_manage_products"), callback_data="manage_products")],
            [types.InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data="all_orders")],
            [types.InlineKeyboardButton(text=t(lang, "menu_manage_registration"), callback_data="manage_registration")],
            [types.InlineKeyboardButton(text=t(lang, "menu_pending_requests"), callback_data="pending_requests")]
        ])
    else:
        # Fallback для других ролей
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t(lang, "menu_catalog"), callback_data="open_catalog")]
        ])

    text = t(lang, "menu_title")
    
    # Проверяем, можем ли редактировать сообщение
    try:
        await message.edit_text(text, reply_markup=kb)
    except:
        # Если не можем редактировать, отправляем новое
        await message.answer(text, reply_markup=kb)

# Команда для возврата в главное меню
@router.callback_query(F.data == "main_menu")
async def back_to_menu(callback: types.CallbackQuery):
    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == str(callback.from_user.id)))
        user = result.scalars().first()
        
        if user:
            await show_main_menu(callback.message, user.lang, user.role)
        else:
            # Пользователь не найден - начать регистрацию заново
            await callback.message.edit_text("Произошла ошибка. Нажмите /start для регистрации.")
    
    await callback.answer()