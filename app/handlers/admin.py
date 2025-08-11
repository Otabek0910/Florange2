from aiogram import Router, types, F

from app.database import get_session
from app.services import UserService, NotificationService
from app.repositories import SettingsRepository
from app.models import RoleEnum, RoleRequest, RequestStatusEnum, RequestedRoleEnum
from app.translate import t
from app.exceptions import UserNotFoundError

router = Router()

async def _get_user_and_check_admin(session, tg_id: int):
    """Получить пользователя и проверить права админа"""
    user_service = UserService(session)
    try:
        user = await user_service.get_user_by_tg_id(str(tg_id))
        is_admin = user.role == RoleEnum.owner
        return user, is_admin
    except UserNotFoundError:
        return None, False

@router.callback_query(F.data == "manage_registration")
async def manage_registration_settings(callback: types.CallbackQuery):
    """Управление настройками регистрации"""
    async for session in get_session():
        user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer(t(user.lang if user else "ru", "access_denied"), show_alert=True)
            return
        
        lang = user.lang or "ru"
        settings_repo = SettingsRepository(session)
        
        # Получаем текущие настройки
        florist_open = await settings_repo.get_bool_value("florist_registration_open", False)
        owner_open = await settings_repo.get_bool_value("owner_registration_open", False)
        
        # Формируем текст и кнопки
        text = (
            f"{t(lang, 'settings_title')}\n\n"
            f"🌸 {t(lang, 'florist_registration')}: {t(lang, 'status_open') if florist_open else t(lang, 'status_closed')}\n"
            f"👑 {t(lang, 'owner_registration')}: {t(lang, 'status_open') if owner_open else t(lang, 'status_closed')}"
        )
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text=f"🔄 {t(lang, 'toggle_florist_reg')}", 
                callback_data="toggle_florist"
            )],
            [types.InlineKeyboardButton(
                text=f"🔄 {t(lang, 'toggle_owner_reg')}", 
                callback_data="toggle_owner"
            )],
            [types.InlineKeyboardButton(
                text=t(lang, "menu_pending_requests"), 
                callback_data="pending_requests"
            )],
            [types.InlineKeyboardButton(
                text=t(lang, "back_to_menu"), 
                callback_data="main_menu"
            )]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()

@router.callback_query(F.data == "toggle_florist")
async def toggle_florist_registration(callback: types.CallbackQuery):
    """Переключить регистрацию флористов"""
    async for session in get_session():
        user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        lang = user.lang or "ru"
        settings_repo = SettingsRepository(session)
        
        # Переключаем настройку
        current = await settings_repo.get_bool_value("florist_registration_open", False)
        new_value = "true" if not current else "false"
        await settings_repo.set_value("florist_registration_open", new_value)
        await session.commit()
        
        await callback.answer(f"✅ Регистрация флористов {'открыта' if not current else 'закрыта'}")
        
        # Обновляем меню
        await manage_registration_settings(callback)

@router.callback_query(F.data == "toggle_owner")
async def toggle_owner_registration(callback: types.CallbackQuery):
    """Переключить регистрацию владельцев"""
    async for session in get_session():
        user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        lang = user.lang or "ru"
        settings_repo = SettingsRepository(session)
        
        # Переключаем настройку
        current = await settings_repo.get_bool_value("owner_registration_open", False)
        new_value = "true" if not current else "false"
        await settings_repo.set_value("owner_registration_open", new_value)
        await session.commit()
        
        await callback.answer(f"✅ Регистрация владельцев {'открыта' if not current else 'закрыта'}")
        
        # Обновляем меню
        await manage_registration_settings(callback)

@router.callback_query(F.data == "pending_requests")
async def show_pending_requests(callback: types.CallbackQuery):
    """Показать ожидающие заявки"""
    async for session in get_session():
        user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        lang = user.lang or "ru"
        user_service = UserService(session)
        
        # Получаем ожидающие заявки
        requests = await user_service.user_repo.get_pending_requests()
        
        if not requests:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="manage_registration")]
            ])
            await callback.message.edit_text(t(lang, "no_pending_requests"), reply_markup=kb)
            await callback.answer()
            return
        
        # Формируем список заявок
        lines = [t(lang, "pending_requests_title"), ""]
        
        for req in requests[:5]:  # Показываем последние 5 заявок
            request_user = await user_service.user_repo.get(req.user_id)
            role_text = t(lang, f"role_{req.requested_role.value}")
            date_str = req.created_at.strftime("%d.%m.%Y %H:%M") if req.created_at else ""
            
            lines.append(
                f"🆔 #{req.id} | {role_text}\n"
                f"👤 {request_user.first_name if request_user else 'N/A'}\n"
                f"💬 {req.reason[:50]}{'...' if len(req.reason) > 50 else ''}\n"
                f"📅 {date_str}\n"
            )
        
        text = "\n".join(lines)
        
        # Кнопки для управления заявками
        buttons = []
        for req in requests[:3]:  # Первые 3 заявки
            request_user = await user_service.user_repo.get(req.user_id)
            role_emoji = "🌸" if req.requested_role == RequestedRoleEnum.florist else "👑"
            buttons.append([
                types.InlineKeyboardButton(
                    text=f"{role_emoji} {request_user.first_name if request_user else 'N/A'} #{req.id}",
                    callback_data=f"view_req_{req.id}"
                )
            ])
        
        buttons.append([types.InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="manage_registration"
        )])
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()

@router.callback_query(F.data.startswith("view_req_"))
async def view_request_details(callback: types.CallbackQuery):
    """Просмотр деталей заявки"""
    request_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        lang = user.lang or "ru"
        user_service = UserService(session)
        
        # Получаем заявку
        from sqlalchemy import select
        result = await session.execute(select(RoleRequest).where(RoleRequest.id == request_id))
        request = result.scalars().first()
        
        if not request:
            await callback.answer(t(lang, "request_not_found"), show_alert=True)
            return
        
        request_user = await user_service.user_repo.get(request.user_id)
        role_text = t(lang, f"role_{request.requested_role.value}")
        date_str = request.created_at.strftime("%d.%m.%Y %H:%M") if request.created_at else ""
        
        text = (
            f"📋 Заявка #{request.id}\n\n"
            f"👤 {request_user.first_name if request_user else 'N/A'} (ID: {request_user.tg_id if request_user else 'N/A'})\n"
            f"🎯 Роль: {role_text}\n"
            f"💬 Причина: {request.reason}\n"
            f"📅 Дата: {date_str}"
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

@router.callback_query(F.data.startswith("approve_req_"))
async def approve_request(callback: types.CallbackQuery):
    """Одобрить заявку на роль"""
    request_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        lang = user.lang or "ru"
        user_service = UserService(session)
        notification_service = NotificationService(callback.bot)
        
        # Получаем заявку
        from sqlalchemy import select, update
        result = await session.execute(select(RoleRequest).where(RoleRequest.id == request_id))
        request = result.scalars().first()
        
        if not request or request.status != RequestStatusEnum.pending:
            await callback.answer(t(lang, "request_not_found"), show_alert=True)
            return
        
        # Получаем пользователя заявки
        request_user = await user_service.user_repo.get(request.user_id)
        
        # Обновляем роль пользователя
        new_role = RoleEnum.florist if request.requested_role == RequestedRoleEnum.florist else RoleEnum.owner
        request_user.role = new_role
        
        # Обновляем статус заявки
        request.status = RequestStatusEnum.approved
        request.approved_by = user.id
        
        await session.commit()
        
        # Уведомляем пользователя
        role_text = t(request_user.lang or "ru", f"role_{request.requested_role.value}")
        try:
            await callback.bot.send_message(
                chat_id=int(request_user.tg_id),
                text=t(request_user.lang or "ru", "role_approved", role=role_text)
            )
        except:
            pass  # Пользователь заблокировал бота
        
        # Обновляем сообщение
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ Одобрено администратором {user.first_name}",
            reply_markup=None
        )
        
        await callback.answer(t(lang, "request_approved"))

@router.callback_query(F.data.startswith("reject_req_"))
async def reject_request(callback: types.CallbackQuery):
    """Отклонить заявку на роль"""
    request_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        lang = user.lang or "ru"
        user_service = UserService(session)
        
        # Получаем заявку
        from sqlalchemy import select
        result = await session.execute(select(RoleRequest).where(RoleRequest.id == request_id))
        request = result.scalars().first()
        
        if not request or request.status != RequestStatusEnum.pending:
            await callback.answer(t(lang, "request_not_found"), show_alert=True)
            return
        
        # Получаем пользователя заявки
        request_user = await user_service.user_repo.get(request.user_id)
        
        # Обновляем статус заявки
        request.status = RequestStatusEnum.rejected
        request.approved_by = user.id
        
        await session.commit()
        
        # Уведомляем пользователя
        role_text = t(request_user.lang or "ru", f"role_{request.requested_role.value}")
        try:
            await callback.bot.send_message(
                chat_id=int(request_user.tg_id),
                text=t(request_user.lang or "ru", "role_rejected", role=role_text)
            )
        except:
            pass
        
        # Обновляем сообщение
        await callback.message.edit_text(
            callback.message.text + f"\n\n❌ Отклонено администратором {user.first_name}",
            reply_markup=None
        )
        
        await callback.answer(t(lang, "request_rejected"))