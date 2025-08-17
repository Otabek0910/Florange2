from aiogram import Router, types, F

from app.database.database import get_session
from app.services import UserService, OrderService
from app.models import RoleEnum, OrderStatusEnum
from app.translate import t
from app.exceptions import UserNotFoundError, OrderNotFoundError
from datetime import datetime

router = Router()

async def _get_user_and_lang(session, tg_id: int):
    """Получить пользователя и язык через сервис"""
    user_service = UserService(session)
    try:
        user = await user_service.get_user_by_tg_id(str(tg_id))
        return user, user.lang or "ru"
    except UserNotFoundError:
        return None, "ru"

@router.callback_query(F.data == "my_orders")
async def show_my_orders(callback: types.CallbackQuery):
    """Показать заказы пользователя (улучшенная версия)"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.message.edit_text(t(lang, "user_not_found"))
            await callback.answer()
            return
        
        order_service = OrderService(session)
        orders = await order_service.get_user_orders(user.id)
        
        if not orders:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
            ])
            await callback.message.edit_text(
                "📝 У вас пока нет заказов\n\n"
                "Закажите букеты в каталоге!",
                reply_markup=kb
            )
            await callback.answer()
            return
        
        # Формируем информативный список заказов
        lines = ["📋 <b>Мои заказы:</b>\n"]
        
        # Группируем заказы по статусам
        status_groups = {}
        total_spent = 0
        
        for order in orders:
            status = order.status.value
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(order)
            total_spent += float(order.total_price or 0)
        
        # Показываем статистику
        lines.append(f"💼 <b>Всего заказов:</b> {len(orders)}")
        lines.append(f"💰 <b>Потрачено:</b> {total_spent:,.0f} сум\n")
        
        # Показываем заказы по статусам
        status_emoji = {
            "new": "🆕",
            "await_florist": "⏳", 
            "accepted": "✅",
            "preparing": "🔄",
            "ready": "🎉",
            "delivering": "🚚",
            "delivered": "✅",
            "canceled": "❌"
        }
        
        for status, group_orders in status_groups.items():
            if not group_orders:
                continue
                
            status_text = t(lang, f"order_status_{status}")
            emoji = status_emoji.get(status, "📦")
            lines.append(f"{emoji} <b>{status_text} ({len(group_orders)}):</b>")
            
            # Показываем последние 3 заказа в каждом статусе
            for order in group_orders[:3]:
                date_str = order.created_at.strftime("%d.%m %H:%M") if order.created_at else ""
                
                # Сокращаем адрес если длинный
                address = order.address or "Не указан"
                if len(address) > 30:
                    address = address[:27] + "..."
                
                lines.append(
                    f"  • <code>#{order.id}</code> | {order.total_price} сум\n"
                    f"    📍 {address} | 📅 {date_str}"
                )
            
            if len(group_orders) > 3:
                lines.append(f"    <i>... и еще {len(group_orders) - 3}</i>")
            lines.append("")
        
        text = "\n".join(lines)
        
        # Добавляем кнопки действий
        kb_rows = []
        
        # Если есть активные заказы - показываем кнопку отслеживания  
        active_statuses = ["new", "await_florist", "accepted", "preparing", "ready", "delivering"]
        has_active = any(order.status.value in active_statuses for order in orders)
        
        if has_active:
            kb_rows.append([types.InlineKeyboardButton(
                text="🔍 Отследить активные", 
                callback_data="track_active_orders"
            )])
        
        # Кнопка повторить последний заказ
        if orders:
            last_order = orders[0]
            kb_rows.append([types.InlineKeyboardButton(
                text=f"🔄 Повторить заказ #{last_order.id}", 
                callback_data=f"repeat_order_{last_order.id}"
            )])
        
        kb_rows.append([types.InlineKeyboardButton(
            text="🏠 Главное меню", 
            callback_data="main_menu"
        )])
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

@router.callback_query(F.data == "florist_orders")
async def show_florist_orders(callback: types.CallbackQuery):
    """Показать новые заказы для флористов"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        # Проверяем права доступа
        if not user or user.role not in [RoleEnum.florist, RoleEnum.owner]:
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        order_service = OrderService(session)
        orders = await order_service.get_orders_for_florist()
        
        if not orders:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
            ])
            await callback.message.edit_text(t(lang, "no_new_orders"), reply_markup=kb)
            await callback.answer()
            return
        
        lines = [t(lang, "new_orders_title"), ""]
        
        for order in orders[:5]:  # Показываем 5 новых заказов
            date_str = order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else ""
            status_text = t(lang, f"order_status_{order.status.value}")
            
            lines.append(
                f"🆔 #{order.id} | {status_text}\n"
                f"💰 {order.total_price} {t(lang, 'currency')}\n"
                f"📍 {order.address}\n"
                f"📞 {order.phone}\n"
                f"📅 {date_str}\n"
            )
        
        text = "\n".join(lines)
        
        # Добавляем кнопки управления для первых заказов
        kb_rows = []
        for order in orders[:3]:  # Управление первыми 3 заказами
            if order.status in [OrderStatusEnum.new, OrderStatusEnum.await_florist]:
                kb_rows.append([
                    types.InlineKeyboardButton(
                        text=f"✅ Принять #{order.id}", 
                        callback_data=f"accept_order_{order.id}"
                    ),
                    types.InlineKeyboardButton(
                        text=f"❌ Отменить #{order.id}", 
                        callback_data=f"cancel_order_{order.id}"
                    )
                ])
        
        kb_rows.append([types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")])
        kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()

@router.callback_query(F.data == "all_orders")
async def show_all_orders(callback: types.CallbackQuery):
    """Показать статистику всех заказов (только для владельца)"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        # Проверяем права владельца
        if not user or user.role != RoleEnum.owner:
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        order_service = OrderService(session)
        
        # Получаем все заказы для статистики
        new_orders = await order_service.get_orders_for_florist()
        
        # TODO: Добавить метод в OrderService для получения всех заказов
        # Пока используем существующие методы
        from sqlalchemy import select
        from app.models import Order
        result = await session.execute(select(Order).order_by(Order.created_at.desc()))
        all_orders = result.scalars().all()
        
        # Группируем по статусам
        status_counts = {}
        total_revenue = 0
        
        for order in all_orders:
            status = order.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            if order.status == OrderStatusEnum.delivered:
                total_revenue += float(order.total_price or 0)
        
        lines = [
            t(lang, "orders_analytics"),
            f"📊 {t(lang, 'total_orders')}: {len(all_orders)}",
            f"💰 {t(lang, 'total_revenue')}: {total_revenue} {t(lang, 'currency')}",
            ""
        ]
        
        for status, count in status_counts.items():
            status_text = t(lang, f"order_status_{status}")
            lines.append(f"{status_text}: {count}")
        
        text = "\n".join(lines)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()

# Управление заказами флористами
@router.callback_query(F.data.startswith("accept_order_"))
async def florist_accept_order(callback: types.CallbackQuery):
    """Флорист принимает заказ"""
    order_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        # Проверяем права доступа
        if not user or user.role not in [RoleEnum.florist, RoleEnum.owner]:
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        order_service = OrderService(session)
        
        try:
            order = await order_service.update_order_status(order_id, OrderStatusEnum.accepted)
            await session.commit()
            
            # Обновляем сообщение
            await callback.answer("✅ Заказ принят")
            
            # Перезагружаем список заказов
            await show_florist_orders(callback)
            
        except OrderNotFoundError:
            await callback.answer(t(lang, "order_not_found"), show_alert=True)
        except Exception as e:
            await callback.answer(f"Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("cancel_order_"))
async def florist_cancel_order(callback: types.CallbackQuery):
    """Флорист отменяет заказ (исправленная версия)"""
    try:
        order_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат команды", show_alert=True)
        return
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        # Проверяем права доступа
        if not user or user.role not in [RoleEnum.florist, RoleEnum.owner]:
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        order_service = OrderService(session)
        
        try:
            # Получаем заказ перед изменением
            order = await order_service.get_order_with_details(order_id)
            
            # Проверяем можно ли отменить
            if order.status in [OrderStatusEnum.delivered, OrderStatusEnum.canceled]:
                await callback.answer("❌ Заказ уже завершен или отменен", show_alert=True)
                return
            
            # Отменяем заказ
            updated_order = await order_service.update_order_status(order_id, OrderStatusEnum.canceled)
            await session.commit()
            
            # Обновляем сообщение С КНОПКОЙ ВОЗВРАТА
            from datetime import datetime
            user_name = getattr(order.user, 'first_name', 'Неизвестно') or 'Неизвестно'
            
            new_text = (
                f"❌ <b>Заказ #{order_id} ОТМЕНЕН</b>\n\n"
                f"👤 Клиент: {user_name}\n"
                f"💰 Сумма: {order.total_price} сум\n"
                f"📞 Телефон: {order.phone}\n"
                f"📍 Адрес: {order.address}\n\n"
                f"🗓 Отменен: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"👤 Отменил: {user.first_name}"
            )
            
            # ДОБАВЛЯЕМ КНОПКУ ВОЗВРАТА
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад к заказам", callback_data="manage_orders")],
                [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
            
            await callback.message.edit_text(new_text, reply_markup=kb, parse_mode="HTML")
            await callback.answer("✅ Заказ отменен")
            
        except OrderNotFoundError:
            await callback.answer("❌ Заказ не найден", show_alert=True)
        except Exception as e:
            print(f"Cancel order error: {e}")
            await callback.answer(f"❌ Ошибка отмены: {str(e)}", show_alert=True)

# Дополнительные статусы для флористов
@router.callback_query(F.data.startswith("ready_order_"))
async def florist_ready_order(callback: types.CallbackQuery):
    """Флорист отмечает заказ готовым"""
    order_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user or user.role not in [RoleEnum.florist, RoleEnum.owner]:
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        order_service = OrderService(session)
        
        try:
            order = await order_service.update_order_status(order_id, OrderStatusEnum.ready)
            await session.commit()
            
            await callback.answer("🎉 Заказ готов к доставке")
            await show_florist_orders(callback)
            
        except OrderNotFoundError:
            await callback.answer(t(lang, "order_not_found"), show_alert=True)
        except Exception as e:
            await callback.answer(f"Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "track_active_orders")
async def track_active_orders(callback: types.CallbackQuery):
    """Отследить активные заказы"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        order_service = OrderService(session)
        orders = await order_service.get_user_orders(user.id)
        
        # Фильтруем только активные заказы
        active_statuses = ["new", "await_florist", "accepted", "preparing", "ready", "delivering"]
        active_orders = [o for o in orders if o.status.value in active_statuses]
        
        if not active_orders:
            await callback.answer("🎉 Нет активных заказов", show_alert=True)
            return
        
        lines = ["🔍 <b>Отслеживание активных заказов:</b>\n"]
        
        for order in active_orders:
            status_text = t(lang, f"order_status_{order.status.value}")
            date_str = order.created_at.strftime("%d.%m %H:%M") if order.created_at else ""
            
            # Определяем этап выполнения
            progress = {
                "new": "▫️▫️▫️▫️▫️",
                "await_florist": "🔵▫️▫️▫️▫️", 
                "accepted": "🔵🔵▫️▫️▫️",
                "preparing": "🔵🔵🔵▫️▫️",
                "ready": "🔵🔵🔵🔵▫️",
                "delivering": "🔵🔵🔵🔵🔵"
            }.get(order.status.value, "▫️▫️▫️▫️▫️")
            
            lines.append(
                f"🆔 <b>#{order.id}</b> | {status_text}\n"
                f"📊 {progress}\n"
                f"💰 {order.total_price} сум | 📅 {date_str}\n"
            )
        
        text = "\n".join(lines)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад к заказам", callback_data="my_orders")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

@router.callback_query(F.data.startswith("repeat_order_"))
async def repeat_order(callback: types.CallbackQuery):
    """Повторить заказ"""
    try:
        order_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат команды", show_alert=True)
        return
    
    await callback.answer("🔄 Функция повтора заказа в разработке", show_alert=True)
    # TODO: Реализовать логику повтора заказа

@router.callback_query(F.data == "manage_orders")
async def manage_orders_callback(callback: types.CallbackQuery):
    """Переход к управлению заказами"""
    await show_florist_orders(callback)