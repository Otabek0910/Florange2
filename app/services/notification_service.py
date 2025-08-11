from typing import List
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import types 
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

    async def notify_florists_about_order(self, florists: List[User], order: Order, lang: str = "ru") -> None:
        """Уведомить флористов о новом заказе"""
        text = (
            f"🆕 Новый заказ #{order.id}\n"
            f"💰 {order.total_price} {t(lang, 'currency')}\n"
            f"📍 {order.address}\n"
            f"📞 {order.phone}\n"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{order.id}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{order.id}")]
        ])
        
        for florist in florists:
            try:
                await self.bot.send_message(chat_id=int(florist.tg_id), text=text, reply_markup=kb)
            except Exception:
                pass
    
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