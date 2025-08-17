from aiogram import Router, types, F

from app.database.database import get_session
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
    try:
        request_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат команды", show_alert=True)
        return
    
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
        
        # Определяем целевую роль
        target_role = RoleEnum.florist if request.requested_role == RequestedRoleEnum.florist else RoleEnum.owner
        
        try:
            # Создаем пользователя с правильными данными
            from app.repositories import UserRepository
            user_repo = UserRepository(session)
            
            # Проверяем существует ли уже пользователь
            existing_user = None
            try:
                from app.services import UserService
                user_service = UserService(session)
                existing_user = await user_service.get_user_by_tg_id(request.user_tg_id)
            except:
                pass
            
            if existing_user:
                # Обновляем роль существующего пользователя
                existing_user.role = target_role
                if not existing_user.first_name and request.first_name:
                    existing_user.first_name = request.first_name
                if not existing_user.last_name and request.last_name:
                    existing_user.last_name = request.last_name
                if not existing_user.phone and request.phone:
                    existing_user.phone = request.phone
                created_user = existing_user
            else:
                # Создаем нового пользователя
                new_user = User(
                    tg_id=request.user_tg_id,
                    first_name=request.first_name or "Неизвестно",
                    last_name=request.last_name,
                    phone=request.phone,
                    lang=request.lang or "ru",
                    role=target_role
                )
                created_user = await user_repo.create(new_user)
            
            # Автоматически создаем профиль флориста если нужно
            if target_role == RoleEnum.florist:
                try:
                    from app.services import FloristService
                    florist_service = FloristService(session)
                    profile = await florist_service.get_or_create_profile(created_user.id)
                    
                    # Устанавливаем текущее время как последнюю активность
                    from datetime import datetime
                    profile.last_seen = datetime.utcnow()
                    profile.is_active = True
                    
                    await session.flush()
                    print(f"✅ Created florist profile for user {created_user.id}")
                except Exception as e:
                    print(f"❌ Florist profile creation error: {e}")
                        
            # Обновляем статус заявки
            request.status = RequestStatusEnum.approved
            request.approved_by = user.id
            
            await session.commit()
            
            # Уведомляем пользователя
            role_name = "флорист" if target_role == RoleEnum.florist else "владелец"
            try:
                await callback.bot.send_message(
                    chat_id=int(request.user_tg_id),
                    text=f"🎉 Ваша заявка на роль '{role_name}' одобрена!\n\nТеперь вам доступны новые функции. Нажмите /start для обновления меню."
                )
            except Exception as e:
                print(f"User notification error: {e}")
            
            # Обновляем сообщение админа
            await callback.message.edit_text(
                f"✅ <b>Заявка #{request_id} ОДОБРЕНА</b>\n\n"
                f"👤 Пользователь: {request.first_name or 'Неизвестно'}\n"
                f"📞 Телефон: {request.phone or 'Не указан'}\n"
                f"🎯 Роль: {role_name}\n"
                f"✅ Одобрил: {user.first_name}\n"
                f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode="HTML"
            )
            
            await callback.answer("✅ Заявка одобрена")
            
        except Exception as e:
            print(f"Approval error: {e}")
            await callback.answer(f"❌ Ошибка одобрения: {str(e)}", show_alert=True)

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


# 2. ДОБАВИТЬ в app/handlers/admin.py - управление флористами

@router.callback_query(F.data == "manage_florists")
async def show_florists_management(callback: types.CallbackQuery):
    """Управление флористами"""
    async for session in get_session():
        user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        lang = user.lang or "ru"
        
        # Получаем всех флористов
        from app.services import UserService
        user_service = UserService(session)
        
        florists = await user_service.user_repo.get_by_role(RoleEnum.florist)
        owners = await user_service.user_repo.get_by_role(RoleEnum.owner)
        
        if not florists and not owners:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
            ])
            await callback.message.edit_text(
                "👥 Флористы и владельцы не найдены",
                reply_markup=kb
            )
            await callback.answer()
            return
        
        lines = ["👥 <b>Управление персоналом:</b>\n"]
        
        if florists:
            lines.append("🌸 <b>Флористы:</b>")
            for florist in florists:
                lines.append(
                    f"• {florist.first_name} {florist.last_name or ''}\n"
                    f"  📞 {florist.phone or 'Не указан'}\n"
                    f"  🆔 ID: {florist.id}"
                )
            lines.append("")
        
        if owners:
            lines.append("👑 <b>Владельцы:</b>")
            for owner in owners:
                if owner.id != user.id:  # Не показываем себя
                    lines.append(
                        f"• {owner.first_name} {owner.last_name or ''}\n"
                        f"  📞 {owner.phone or 'Не указан'}\n"
                        f"  🆔 ID: {owner.id}"
                    )
            lines.append("")
        
        text = "\n".join(lines)
        
        # Кнопки управления для флористов
        kb_rows = []
        
        for florist in florists[:4]:  # Первые 4 флориста
            kb_rows.append([
                types.InlineKeyboardButton(text=f"👤 {florist.first_name}", callback_data=f"user_info_{florist.id}"),
                types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_florist_{florist.id}")
            ])

        
        if len(florists) > 4:
            kb_rows.append([types.InlineKeyboardButton(text="📋 Показать всех", callback_data="show_all_florists")])
        
        kb_rows.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

@router.callback_query(F.data.startswith("user_info_"))
async def show_user_info(callback: types.CallbackQuery):
    """Показать информацию о пользователе"""
    try:
        user_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат команды", show_alert=True)
        return
    
    async for session in get_session():
        admin_user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        from app.services import UserService, OrderService
        user_service = UserService(session)
        order_service = OrderService(session)
        
        try:
            target_user = await user_service.get_user_by_id(user_id)
            
            # Получаем статистику заказов пользователя
            user_orders = await order_service.get_user_orders(user_id)
            
            total_orders = len(user_orders)
            total_spent = sum(float(order.total_price or 0) for order in user_orders)
            
            role_emoji = {"florist": "🌸", "owner": "👑", "client": "👤"}.get(target_user.role.value, "❓")
            
            # КОРОТКАЯ информация
            text = (
                f"{role_emoji} <b>Профиль</b>\n\n"
                f"👤 {target_user.first_name} {target_user.last_name or ''}\n"
                f"📞 {target_user.phone or 'Не указан'}\n"
                f"🎯 {target_user.role.value}\n"
                f"🗓 {target_user.created_at.strftime('%d.%m.%Y') if target_user.created_at else 'Неизвестно'}\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Заказов: {total_orders}\n"
                f"• Потратил: {total_spent:,.0f} сум"
            )
            
            kb_rows = []
            
            # Кнопка удаления (только не для себя)
            if target_user.id != admin_user.id:
                kb_rows.append([
                    types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_florist_{user_id}")
                ])
            
            kb_rows.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_florists")])
            
            kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
            
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            await callback.answer()
            
        except Exception as e:
            await callback.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

@router.callback_query(F.data.startswith("delete_florist_"))
async def delete_florist_confirm(callback: types.CallbackQuery):
    """Подтверждение удаления флориста"""
    try:
        user_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат команды", show_alert=True)
        return
    
    async for session in get_session():
        admin_user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        from app.services import UserService
        user_service = UserService(session)
        
        try:
            target_user = await user_service.get_user_by_id(user_id)
            
            # Проверяем что это флорист
            if target_user.role not in [RoleEnum.florist, RoleEnum.owner]:
                await callback.answer("❌ Можно удалять только флористов", show_alert=True)
                return
            
            # Нельзя удалить себя
            if target_user.id == admin_user.id:
                await callback.answer("❌ Нельзя удалить себя", show_alert=True)
                return
            
            # КОРОТКОЕ подтверждение
            confirm_text = (
                f"⚠️ <b>Удаление флориста</b>\n\n"
                f"👤 {target_user.first_name} {target_user.last_name or ''}\n"
                f"📞 {target_user.phone or 'Не указан'}\n\n"
                f"🗑 <b>Что произойдет:</b>\n"
                f"• Пользователь удален из системы\n"
                f"• История работы сохранится\n"
                f"• Сможет зарегистрироваться как клиент\n\n"
                f"❓ Продолжить?"
            )
            
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"confirm_delete_{user_id}"),
                    types.InlineKeyboardButton(text="❌ Отмена", callback_data="manage_florists")
                ]
            ])
            
            await callback.message.edit_text(confirm_text, reply_markup=kb, parse_mode="HTML")
            await callback.answer()
            
        except Exception as e:
            await callback.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_florist(callback: types.CallbackQuery):
    """Подтвердить удаление флориста"""
    try:
        user_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат команды", show_alert=True)
        return
    
    async for session in get_session():
        admin_user, is_admin = await _get_user_and_check_admin(session, callback.from_user.id)
        
        if not is_admin:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        from app.services import UserService
        user_service = UserService(session)
        
        try:
            target_user = await user_service.get_user_by_id(user_id)
            user_name = f"{target_user.first_name} {target_user.last_name or ''}".strip()
            
            # Уведомляем пользователя ДО удаления (короткое сообщение)
            try:
                await callback.bot.send_message(
                    chat_id=int(target_user.tg_id),
                    text=(
                        f"📢 Ваш аккаунт флориста удален.\n\n"
                        f"💡 Можете зарегистрироваться заново как клиент: /start"
                    )
                )
            except Exception as e:
                print(f"User notification error: {e}")
            
            # ПОЛНОЕ УДАЛЕНИЕ из системы
            await _delete_user_completely(session, user_id)
            await session.commit()
            
            # Показываем КОРОТКИЙ результат
            result_text = (
                f"✅ <b>Флорист удален</b>\n\n"
                f"👤 {user_name}\n"
                f"🗑 ID: {user_id}\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"👤 Выполнил: {admin_user.first_name}"
            )
            
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_florists")]
            ])
            
            await callback.message.edit_text(result_text, reply_markup=kb, parse_mode="HTML")
            await callback.answer("✅ Флорист удален")
            
        except Exception as e:
            error_msg = str(e)
            # Укорачиваем сообщение об ошибке
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            
            print(f"Delete error: {e}")
            await callback.answer(f"❌ Ошибка: {error_msg}", show_alert=True)

async def _delete_user_completely(session, user_id: int):
    """Полное удаление пользователя из системы"""
    from sqlalchemy import delete, update
    from app.models import User, RoleRequest, FloristProfile
    
    try:
        # 1. СНАЧАЛА удаляем/обновляем все ссылки на пользователя
        
        # Удаляем заявки где пользователь подавал заявку (по tg_id)
        target_user = await session.get(User, user_id)
        if target_user:
            await session.execute(
                delete(RoleRequest).where(RoleRequest.user_tg_id == target_user.tg_id)
            )
        
        # Обновляем заявки где пользователь был одобряющим (оставляем для истории)
        await session.execute(
            update(RoleRequest)
            .where(RoleRequest.approved_by == user_id)
            .values(approved_by=None)
        )
        
        # 2. Удаляем профиль флориста (если есть)
        try:
            await session.execute(
                delete(FloristProfile).where(FloristProfile.user_id == user_id)
            )
        except Exception:
            # Если таблицы FloristProfile нет - игнорируем
            pass
        
        # 3. ИСТОРИЯ ЗАКАЗОВ И КОНСУЛЬТАЦИЙ ОСТАЕТСЯ!
        # orders.user_id остается для отчетности
        # В интерфейсе будет показываться "Удаленный пользователь"
        
        # 4. ПОСЛЕДНИМ удаляем самого пользователя
        await session.execute(
            delete(User).where(User.id == user_id)
        )
        
        print(f"User {user_id} completely deleted from system")
        
    except Exception as e:
        print(f"Complete deletion error: {e}")
        raise