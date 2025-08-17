from typing import List
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import types
from datetime import datetime

from app.models import User, Order, RoleRequest
from app.translate import t

class NotificationService:
    """Сервис уведомлений"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def notify_admins_about_role_request(self, admins: List[User], request: RoleRequest) -> None:
        """Уведомить админов о заявке на роль"""
        
        # Парсим данные пользователя
        try:
            user_data = eval(request.user_data)
            full_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
            phone = user_data.get('phone', 'Не указан')
            lang = user_data.get('lang', 'ru')
        except:
            full_name = "Ошибка данных"
            phone = "Не указан"
            lang = "ru"
        
        # Переводим роль на человеческий язык
        role_names = {
            "florist": {"ru": "Флорист", "uz": "Florist"},
            "owner": {"ru": "Владелец", "uz": "Egasi"}
        }
        
        role_text = role_names.get(request.requested_role.value, {}).get("ru", "Неизвестная роль")
        
        for admin in admins:
            try:
                text = (
                    f"🆕 Новая заявка на роль\n\n"
                    f"👤 Пользователь: {full_name}\n"
                    f"📞 Телефон: {phone}\n"
                    f"🎯 Роль: {role_text}\n"
                    f"🆔 Telegram ID: {request.user_tg_id}\n"
                )
                
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_req_{request.id}")],
                    [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_req_{request.id}")]
                ])
                
                await self.bot.send_message(chat_id=int(admin.tg_id), text=text, reply_markup=kb)
            except Exception as e:
                print(f"Error sending notification to admin {admin.tg_id}: {e}")
    
    async def notify_florists_about_order(self, florists: list, order, lang: str):
        """Уведомить флористов о новом заказе С ПОДРОБНОСТЯМИ"""
        user_name = getattr(order.user, 'first_name', 'Неизвестно') or 'Неизвестно'
        
        # ПОЛУЧАЕМ ДЕТАЛИ ЗАКАЗА (позиции) - ИСПРАВЛЕННАЯ ЛОГИКА
        order_items = []
        try:
            if hasattr(order, 'items') and order.items:
                for item in order.items:
                    if hasattr(item, 'product') and item.product:
                        product_name = item.product.name_ru if lang == "ru" else item.product.name_uz
                        order_items.append(f"• {product_name} × {item.qty}")
                    else:
                        order_items.append(f"• Товар ID:{item.product_id} × {item.qty}")
        except Exception as e:
            print(f"Error getting order items: {e}")
        
        items_text = "\n".join(order_items) if order_items else "Позиции заказа недоступны"
        
        # ИНФОРМАТИВНОЕ УВЕДОМЛЕНИЕ
        message = (
            f"🆕 <b>Новый заказ #{order.id}</b>\n\n"
            f"👤 <b>Клиент:</b> {user_name}\n"
            f"📞 <b>Телефон:</b> {order.phone}\n"
            f"📍 <b>Адрес:</b> {order.address}\n"
            f"💰 <b>Сумма:</b> {order.total_price} сум\n"
            f"🗓 <b>Создан:</b> {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🛍 <b>Состав заказа:</b>\n{items_text}\n\n"
            f"💬 <b>Комментарий:</b> {order.comment or 'Нет'}\n\n"
            f"📋 Управляйте заказом через меню 'Управление заказами'"
        )
        
        print(f"📧 Отправляем уведомление: {message[:100]}...")
        
        for florist in florists:
            try:
                await self.bot.send_message(
                    chat_id=int(florist.tg_id),
                    text=message,
                    parse_mode="HTML"
                )
                print(f"✅ Уведомление отправлено флористу {florist.tg_id}")
            except Exception as e:
                print(f"❌ Failed to notify florist {florist.tg_id}: {e}")
    
    async def notify_user_about_order_status(self, user: User, order: Order) -> None:
        """Уведомить пользователя об изменении статуса заказа"""
        lang = user.lang or "ru"
        status_text = t(lang, f"order_status_{order.status.value}")
        
        text = (
            f"📦 Заказ #{order.id}\n"
            f"Статус: {status_text}\n"
        )
        
        try:
            await self.bot.send_message(chat_id=int(user.tg_id), text=text)
        except Exception:
            pass

    async def notify_order_status_change(self, order, new_status: str, changed_by_user, lang: str = "ru"):
        """Уведомить о смене статуса заказа"""
        from app.models import RoleEnum
        
        # Получаем всех владельцев для уведомления
        from app.database.database import get_session
        from app.services import UserService
        
        async for session in get_session():
            user_service = UserService(session)
            owners = await user_service.user_repo.get_by_role(RoleEnum.owner)
            florists = await user_service.user_repo.get_by_role(RoleEnum.florist)
            
            status_emoji = {
                "accepted": "✅ ПРИНЯТ",
                "canceled": "❌ ОТМЕНЕН", 
                "preparing": "🔄 ГОТОВИТСЯ",
                "ready": "🎉 ГОТОВ",
                "delivering": "🚚 ДОСТАВЛЯЕТСЯ",
                "delivered": "✅ ДОСТАВЛЕН"
            }
            
            status_text = status_emoji.get(new_status, new_status.upper())
            changer_name = f"{changed_by_user.first_name} {changed_by_user.last_name or ''}".strip()
            changer_role = "👑 Владелец" if changed_by_user.role == RoleEnum.owner else "🌸 Флорист"
            
            message = (
                f"📢 <b>Изменение статуса заказа</b>\n\n"
                f"🆔 <b>Заказ:</b> #{order.id}\n"
                f"📊 <b>Статус:</b> {status_text}\n"
                f"👤 <b>Изменил:</b> {changer_name} ({changer_role})\n"
                f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"💰 Сумма: {order.total_price} сум\n"
                f"📍 Адрес: {order.address}"
            )
            
            # Уведомляем владельцев (они видят кто принял)
            for owner in owners:
                try:
                    await self.bot.send_message(
                        chat_id=int(owner.tg_id),
                        text=message,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"Failed to notify owner {owner.tg_id}: {e}")
            
            # Флористов уведомляем только если заказ принят (чтобы они знали что заказ занят)
            if new_status in ["accepted", "canceled"]:
                simple_message = (
                    f"📢 Заказ #{order.id} {status_text}\n"
                    f"👤 Принял: {changer_name}"
                )
                
                for florist in florists:
                    # НЕ уведомляем того кто принял заказ
                    if florist.id != changed_by_user.id:
                        try:
                            await self.bot.send_message(
                                chat_id=int(florist.tg_id),
                                text=simple_message,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            print(f"Failed to notify florist {florist.tg_id}: {e}")

    async def hide_order_from_other_florists(self, order_id: int, taken_by_user):
        """Скрыть заказ у других флористов после принятия"""
        from app.database.database import get_session
        from app.services import UserService
        from app.models import RoleEnum
        
        async for session in get_session():
            user_service = UserService(session)
            florists = await user_service.user_repo.get_by_role(RoleEnum.florist)
            
            hide_message = (
                f"🔒 <b>Заказ #{order_id} принят</b>\n\n"
                f"👤 Принял: {taken_by_user.first_name}\n"
                f"📊 Заказ больше недоступен для принятия"
            )
            
            for florist in florists:
                # НЕ отправляем тому кто принял
                if florist.id != taken_by_user.id:
                    try:
                        await self.bot.send_message(
                            chat_id=int(florist.tg_id),
                            text=hide_message,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        print(f"Failed to hide order from florist {florist.tg_id}: {e}")