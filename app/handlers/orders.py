from aiogram import Router, types, F

from app.database import get_session
from app.services import UserService, OrderService
from app.models import RoleEnum, OrderStatusEnum
from app.translate import t
from app.exceptions import UserNotFoundError, OrderNotFoundError

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
    """Показать заказы пользователя"""
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
            await callback.message.edit_text(t(lang, "no_orders"), reply_markup=kb)
            await callback.answer()
            return
        
        # Формируем список заказов
        lines = [t(lang, "my_orders_title"), ""]
        
        for order in orders[:10]:  # Показываем последние 10 заказов
            status_text = t(lang, f"order_status_{order.status.value}")
            date_str = order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else ""
            
            lines.append(
                f"🆔 #{order.id} | {status_text}\n"
                f"💰 {order.total_price} {t(lang, 'currency')}\n"
                f"📅 {date_str}\n"
            )
        
        text = "\n".join(lines)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb)
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
    """Флорист отменяет заказ"""
    order_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        # Проверяем права доступа
        if not user or user.role not in [RoleEnum.florist, RoleEnum.owner]:
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        order_service = OrderService(session)
        
        try:
            order = await order_service.update_order_status(order_id, OrderStatusEnum.canceled)
            await session.commit()
            
            # Обновляем сообщение
            await callback.answer("❌ Заказ отменен")
            
            # Перезагружаем список заказов
            await show_florist_orders(callback)
            
        except OrderNotFoundError:
            await callback.answer(t(lang, "order_not_found"), show_alert=True)
        except Exception as e:
            await callback.answer(f"Ошибка: {str(e)}", show_alert=True)

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