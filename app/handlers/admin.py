from aiogram import Router, types, F
from sqlalchemy import select, update
from app.database import get_session
from app.models import User, RoleRequest, Settings, RoleEnum, RequestStatusEnum, RequestedRoleEnum
from app.translate import t

router = Router()

async def _get_user_lang(session, tg_id: int) -> str:
    res = await session.execute(select(User).where(User.tg_id == str(tg_id)))
    user = res.scalars().first()
    return (user.lang or "ru") if user else "ru"

async def _is_admin(session, tg_id: int) -> bool:
    """Проверка, является ли пользователь администратором (владельцем)"""
    res = await session.execute(select(User).where(User.tg_id == str(tg_id)))
    user = res.scalars().first()
    return user and user.role == RoleEnum.owner

# Обработка заявок на роли
@router.callback_query(F.data.startswith("approve_req_"))
async def approve_request(callback: types.CallbackQuery):
    request_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        if not await _is_admin(session, callback.from_user.id):
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        # Получаем заявку
        request_result = await session.execute(select(RoleRequest).where(RoleRequest.id == request_id))
        request = request_result.scalars().first()
        
        if not request or request.status != RequestStatusEnum.pending:
            await callback.answer(t(lang, "request_not_found"), show_alert=True)
            return
        
        # Получаем пользователя
        user = await session.get(User, request.user_id)
        admin = await session.execute(select(User).where(User.tg_id == str(callback.from_user.id)))
        admin_user = admin.scalars().first()
        
        # Обновляем роль пользователя
        new_role = RoleEnum.florist if request.requested_role == RequestedRoleEnum.florist else RoleEnum.owner
        
        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(role=new_role)
        )
        
        # Обновляем статус заявки
        await session.execute(
            update(RoleRequest)
            .where(RoleRequest.id == request_id)
            .values(
                status=RequestStatusEnum.approved,
                approved_by=admin_user.id
            )
        )
        
        await session.commit()
        
        # Уведомляем пользователя
        role_text = t(user.lang, f"role_{request.requested_role.value}")
        try:
            await callback.bot.send_message(
                chat_id=int(user.tg_id),
                text=t(user.lang, "role_approved", role=role_text)
            )
        except:
            pass  # Пользователь заблокировал бота
        
        # Обновляем сообщение админа
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ Одобрено администратором {admin_user.first_name}",
            reply_markup=None
        )
        
        await callback.answer(t(lang, "request_approved"))

@router.callback_query(F.data.startswith("reject_req_"))
async def reject_request(callback: types.CallbackQuery):
    request_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        if not await _is_admin(session, callback.from_user.id):
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        # Получаем заявку
        request_result = await session.execute(select(RoleRequest).where(RoleRequest.id == request_id))
        request = request_result.scalars().first()
        
        if not request or request.status != RequestStatusEnum.pending:
            await callback.answer(t(lang, "request_not_found"), show_alert=True)
            return
        
        # Получаем пользователя
        user = await session.get(User, request.user_id)
        admin = await session.execute(select(User).where(User.tg_id == str(callback.from_user.id)))
        admin_user = admin.scalars().first()
        
        # Обновляем статус заявки
        await session.execute(
            update(RoleRequest)
            .where(RoleRequest.id == request_id)
            .values(
                status=RequestStatusEnum.rejected,
                approved_by=admin_user.id
            )
        )
        
        await session.commit()
        
        # Уведомляем пользователя
        role_text = t(user.lang, f"role_{request.requested_role.value}")
        try:
            await callback.bot.send_message(
                chat_id=int(user.tg_id),
                text=t(user.lang, "role_rejected", role=role_text)
            )
        except:
            pass
        
        # Обновляем сообщение админа
        await callback.message.edit_text(
            callback.message.text + f"\n\n❌ Отклонено администратором {admin_user.first_name}",
            reply_markup=None
        )
        
        await callback.answer(t(lang, "request_rejected"))

# Управление настройками регистрации
@router.callback_query(F.data == "manage_registration")
async def manage_registration_settings(callback: types.CallbackQuery):
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        if not await _is_admin(session, callback.from_user.id):
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        # Получаем текущие настройки
        florist_setting = await session.execute(
            select(Settings).where(Settings.key == "florist_registration_open")
        )
        owner_setting = await session.execute(
            select(Settings).where(Settings.key == "owner_registration_open")
        )
        
        florist_open = florist_setting.scalars().first()
        owner_open = owner_setting.scalars().first()
        
        is_florist_open = florist_open and florist_open.value == "true"
        is_owner_open = owner_open and owner_open.value == "true"
        
        # Формируем клавиатуру
        buttons = []
        
        florist_text = t(lang, "close_florist_reg") if is_florist_open else t(lang, "open_florist_reg")
        owner_text = t(lang, "close_owner_reg") if is_owner_open else t(lang, "open_owner_reg")
        
        buttons.append([types.InlineKeyboardButton(
            text=florist_text, 
            callback_data=f"toggle_florist_reg_{not is_florist_open}"
        )])
        buttons.append([types.InlineKeyboardButton(
            text=owner_text,
            callback_data=f"toggle_owner_reg_{not is_owner_open}"
        )])
        buttons.append([types.InlineKeyboardButton(
            text=t(lang, "back_to_menu"),
            callback_data="main_menu"
        )])
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
        
        text = t(lang, "registration_settings", 
                florist_status=t(lang, "open") if is_florist_open else t(lang, "closed"),
                owner_status=t(lang, "open") if is_owner_open else t(lang, "closed"))
        
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()

@router.callback_query(F.data.startswith("toggle_florist_reg_"))
async def toggle_florist_registration(callback: types.CallbackQuery):
    new_value = callback.data.split("_")[3] == "True"
    
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        if not await _is_admin(session, callback.from_user.id):
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        await session.execute(
            update(Settings)
            .where(Settings.key == "florist_registration_open")
            .values(value=str(new_value).lower())
        )
        await session.commit()
        
        status = t(lang, "opened") if new_value else t(lang, "closed")
        await callback.answer(t(lang, "florist_registration_toggled", status=status))
        
# Просмотр всех заявок
@router.callback_query(F.data == "pending_requests")
async def show_pending_requests(callback: types.CallbackQuery):
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        if not await _is_admin(session, callback.from_user.id):
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        # Получаем все ожидающие заявки
        requests_result = await session.execute(
            select(RoleRequest)
            .where(RoleRequest.status == RequestStatusEnum.pending)
            .order_by(RoleRequest.created_at.desc())
        )
        requests = requests_result.scalars().all()
        
        if not requests:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
            ])
            await callback.message.edit_text(t(lang, "no_pending_requests"), reply_markup=kb)
            await callback.answer()
            return
        
        lines = [t(lang, "pending_requests_title"), ""]
        
        for req in requests[:10]:  # Показываем последние 10 заявок
            user = await session.get(User, req.user_id)
            role_text = t(lang, f"role_{req.requested_role.value}")
            date_str = req.created_at.strftime("%d.%m.%Y %H:%M") if req.created_at else ""
            
            lines.append(
                f"🆔 #{req.id} | {role_text}\n"
                f"👤 {user.first_name if user else 'N/A'}\n"
                f"💬 {req.reason[:50]}{'...' if len(req.reason) > 50 else ''}\n"
                f"📅 {date_str}\n"
            )
        
        text = "\n".join(lines)
        
        # Добавляем кнопки для быстрого управления первыми заявками
        buttons = []
        for req in requests[:3]:  # Первые 3 заявки
            user = await session.get(User, req.user_id)
            role_emoji = "🌸" if req.requested_role == RequestedRoleEnum.florist else "👑"
            buttons.append([
                types.InlineKeyboardButton(
                    text=f"{role_emoji} {user.first_name if user else 'N/A'} #{req.id}",
                    callback_data=f"view_req_{req.id}"
                )
            ])
        
        buttons.append([types.InlineKeyboardButton(
            text=t(lang, "back_to_menu"),
            callback_data="main_menu"
        )])
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()

@router.callback_query(F.data.startswith("view_req_"))
async def view_request_details(callback: types.CallbackQuery):
    request_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        if not await _is_admin(session, callback.from_user.id):
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        # Получаем заявку
        request_result = await session.execute(select(RoleRequest).where(RoleRequest.id == request_id))
        request = request_result.scalars().first()
        
        if not request:
            await callback.answer(t(lang, "request_not_found"), show_alert=True)
            return
        
        user = await session.get(User, request.user_id)
        role_text = t(lang, f"role_{request.requested_role.value}")
        date_str = request.created_at.strftime("%d.%m.%Y %H:%M") if request.created_at else ""
        
        text = (
            f"📋 Заявка #{request.id}\n\n"
            f"👤 {user.first_name if user else 'N/A'} (@{user.tg_id if user else 'N/A'})\n"
            f"🎯 Роль: {role_text}\n"
            f"💬 Причина: {request.reason}\n"
            f"📅 Дата: {date_str}\n"
            f"📊 Статус: {t(lang, f'request_status_{request.status.value}')}"
        )
        
        if request.status == RequestStatusEnum.pending:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_req_{request.id}")],
                [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_req_{request.id}")],
                [types.InlineKeyboardButton(text="↩️ К списку", callback_data="pending_requests")]
            ])
        else:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="↩️ К списку", callback_data="pending_requests")]
            ])
        
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()



@router.callback_query(F.data.startswith("toggle_owner_reg_"))
async def toggle_owner_registration(callback: types.CallbackQuery):
    new_value = callback.data.split("_")[3] == "True"
    
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        if not await _is_admin(session, callback.from_user.id):
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        await session.execute(
            update(Settings)
            .where(Settings.key == "owner_registration_open")
            .values(value=str(new_value).lower())
        )
        await session.commit()
        
        status = t(lang, "opened") if new_value else t(lang, "closed")
        await callback.answer(t(lang, "owner_registration_toggled", status=status))
        
        # Обновляем сообщение
        await manage_registration_settings(callback)