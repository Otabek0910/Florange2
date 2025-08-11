from aiogram import Router, types, F
from sqlalchemy import select
from app.database import get_session
from app.models import User, Order, OrderItem, Product
from app.translate import t

router = Router()

async def _get_user_lang(session, tg_id: int) -> str:
    res = await session.execute(select(User).where(User.tg_id == str(tg_id)))
    user = res.scalars().first()
    return (user.lang or "ru") if user else "ru"

@router.callback_query(F.data == "my_orders")
async def show_my_orders(callback: types.CallbackQuery):
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        # Получаем пользователя
        user_result = await session.execute(select(User).where(User.tg_id == str(callback.from_user.id)))
        user = user_result.scalars().first()
        
        if not user:
            await callback.message.edit_text(t(lang, "user_not_found"))
            await callback.answer()
            return
        
        # Получаем заказы пользователя
        orders_result = await session.execute(
            select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
        )
        orders = orders_result.scalars().all()
        
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

# Для флористов - просмотр новых заказов
@router.callback_query(F.data == "florist_orders")
async def show_florist_orders(callback: types.CallbackQuery):
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        # Получаем новые заказы
        orders_result = await session.execute(
            select(Order).where(Order.status.in_(["new", "await_florist"])).order_by(Order.created_at.desc())
        )
        orders = orders_result.scalars().all()
        
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
            
            lines.append(
                f"🆔 #{order.id}\n"
                f"💰 {order.total_price} {t(lang, 'currency')}\n"
                f"📍 {order.address}\n"
                f"📞 {order.phone}\n"
                f"📅 {date_str}\n"
            )
        
        text = "\n".join(lines)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()

# Для владельца - все заказы
@router.callback_query(F.data == "all_orders")
async def show_all_orders(callback: types.CallbackQuery):
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        # Получаем статистику заказов
        orders_result = await session.execute(select(Order).order_by(Order.created_at.desc()))
        orders = orders_result.scalars().all()
        
        # Группируем по статусам
        status_counts = {}
        total_revenue = 0
        
        for order in orders:
            status = order.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            if order.status.value in ["delivered"]:
                total_revenue += float(order.total_price or 0)
        
        lines = [
            t(lang, "orders_analytics"),
            f"📊 {t(lang, 'total_orders')}: {len(orders)}",
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