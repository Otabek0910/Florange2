from aiogram import Router, types, F

from app.database import get_session
from app.services import UserService, NotificationService
from app.repositories import SettingsRepository
from app.models import (
    RoleEnum, 
    RoleRequest, 
    RequestStatusEnum, 
    RequestedRoleEnum,
    User  # Для создания пользователей при одобрении
)
from app.translate import t
from app.exceptions import UserNotFoundError

import logging
from datetime import datetime
from app.translate import t
from app.models import User, RoleEnum, RequestedRoleEnum

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
        
        # Получаем ожидающие заявки
        from sqlalchemy import select
        result = await session.execute(
            select(RoleRequest).where(RoleRequest.status == RequestStatusEnum.pending)
        )
        requests = result.scalars().all()
        
        if not requests:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="manage_registration")]
            ])
            await callback.message.edit_text(t(lang, "no_pending_requests"), reply_markup=kb)
            await callback.answer()
            return
        
        # Переводы ролей
        role_names = {
            "florist": {"ru": "🌸 Флорист", "uz": "🌸 Florist"},
            "owner": {"ru": "👑 Владелец", "uz": "👑 Egasi"}
        }
        
        # Формируем список заявок
        lines = [t(lang, "pending_requests_title"), ""]
        
        for req in requests[:5]:  # Показываем последние 5 заявок
            role_text = role_names.get(req.requested_role.value, {}).get(lang, req.requested_role.value)
            date_str = req.created_at.strftime("%d.%m.%Y %H:%M") if req.created_at else ""
            
            # Парсим данные пользователя
            try:
                user_data = eval(req.user_data)
                full_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                phone = user_data.get('phone', 'Не указан')
            except:
                full_name = "Ошибка данных"
                phone = "Не указан"
            
            lines.append(
                f"🆔 #{req.id} | {role_text}\n"
                f"👤 {full_name}\n"
                f"📞 {phone}\n"
                f"📅 {date_str}\n"
            )
        
        text = "\n".join(lines)
        
        # Кнопки для управления заявками
        buttons = []
        for req in requests[:3]:  # Первые 3 заявки
            try:
                user_data = eval(req.user_data)
                display_name = user_data.get('first_name', 'Без имени')
            except:
                display_name = "N/A"
            
            role_emoji = "🌸" if req.requested_role == RequestedRoleEnum.florist else "👑"
            buttons.append([
                types.InlineKeyboardButton(
                    text=f"{role_emoji} {display_name} #{req.id}",
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
        
        # Получаем заявку
        from sqlalchemy import select
        result = await session.execute(select(RoleRequest).where(RoleRequest.id == request_id))
        request = result.scalars().first()
        
        if not request:
            await callback.answer(t(lang, "request_not_found"), show_alert=True)
            return
        
        # Переводы ролей
        role_names = {
            "florist": {"ru": "Флорист", "uz": "Florist"},
            "owner": {"ru": "Владелец", "uz": "Egasi"}
        }
        
        role_text = role_names.get(request.requested_role.value, {}).get(lang, request.requested_role.value)
        date_str = request.created_at.strftime("%d.%m.%Y %H:%M") if request.created_at else ""
        
        # Парсим данные пользователя
        try:
            user_data = eval(request.user_data)
            full_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
            phone = user_data.get('phone', 'Не указан')
        except:
            full_name = "Ошибка данных"
            phone = "Не указан"
        
        text = (
            f"📋 Заявка #{request.id}\n\n"
            f"👤 {full_name}\n"
            f"📞 {phone}\n"
            f"🆔 Telegram ID: {request.user_tg_id}\n"
            f"🎯 Роль: {role_text}\n"
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
        
        # Получаем заявку
        from sqlalchemy import select
        result = await session.execute(select(RoleRequest).where(RoleRequest.id == request_id))
        request = result.scalars().first()
        
        if not request or request.status != RequestStatusEnum.pending:
            await callback.answer(t(lang, "request_not_found"), show_alert=True)
            return
        
        # ✅ БЕЗОПАСНО: используем структурированные поля
        user_data = {
            "tg_id": request.user_tg_id,
            "first_name": request.first_name,
            "last_name": request.last_name,
            "phone": request.phone,
            "lang": request.lang or "ru"
        }
        
        # Создаем пользователя с нужной ролью
        target_role = RoleEnum.florist if request.requested_role == RequestedRoleEnum.florist else RoleEnum.owner
        
        try:
            new_user = User(
                tg_id=request.user_tg_id,
                first_name=request.first_name,
                last_name=request.last_name,
                phone=request.phone,
                lang=request.lang,
                role=target_role
            )
            
            from app.repositories import UserRepository
            user_repo = UserRepository(session)
            created_user = await user_repo.create(new_user)
            
            # Автоматически создаем профиль флориста
            if target_role == RoleEnum.florist:
                from app.services import FloristService
                florist_service = FloristService(session)
                await florist_service.get_or_create_profile(created_user.id)
            
            # Обновляем заявку
            request.status = RequestStatusEnum.approved
            request.approved_by = user.id
            request.user_id = created_user.id
            
            await session.commit()
            
            # Уведомляем пользователя
            role_text = t(user_data["lang"], f"role_{request.requested_role.value}")
            await callback.bot.send_message(
                chat_id=int(user_data["tg_id"]),
                text=t(user_data["lang"], "role_approved", role=role_text)
            )
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Error approving request: {e}")
            await callback.answer("Ошибка при одобрении заявки", show_alert=True)
            return

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
        
        # Получаем заявку
        from sqlalchemy import select
        result = await session.execute(select(RoleRequest).where(RoleRequest.id == request_id))
        request = result.scalars().first()
        
        if not request or request.status != RequestStatusEnum.pending:
            await callback.answer(t(lang, "request_not_found"), show_alert=True)
            return
        
        # Парсим данные пользователя для уведомления
        try:
            user_data = eval(request.user_data)
        except:
            user_data = {"tg_id": request.user_tg_id, "lang": "ru"}
        
        # Обновляем статус заявки
        request.status = RequestStatusEnum.rejected
        request.approved_by = user.id
        
        await session.commit()
        
        # ВАЖНО: При отклонении НЕ создаем пользователя вообще!
        # Пользователь останется незарегистрированным
        
        # Уведомляем пользователя об отклонении
        role_text = t(user_data.get("lang", "ru"), f"role_{request.requested_role.value}")
        try:
            await callback.bot.send_message(
                chat_id=int(user_data["tg_id"]),
                text=t(user_data.get("lang", "ru"), "role_rejected", role=role_text) + 
                     f"\n\n{t(user_data.get('lang', 'ru'), 'can_register_as_client')}"
            )
        except:
            pass
        
        await callback.message.edit_text(
            callback.message.text + f"\n\n❌ Отклонено администратором {user.first_name}",
            reply_markup=None
        )
        
        await callback.answer(t(lang, "request_rejected"))
