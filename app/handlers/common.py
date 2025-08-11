"""Общие функции для обработчиков"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.models import User
from app.translate import t

async def create_main_menu_keyboard(user: User) -> InlineKeyboardMarkup:
    """Создать клавиатуру главного меню"""
    lang = user.lang or "ru"
    role = user.role
    
    kb_rows = [
        [InlineKeyboardButton(text=t(lang, "menu_catalog"), callback_data="open_catalog")],
        [InlineKeyboardButton(text=t(lang, "menu_cart"), callback_data="open_cart")],
        [InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data="my_orders")]
    ]
    
    # Добавляем админские кнопки для владельца
    if role == "owner":
        kb_rows.extend([
            [InlineKeyboardButton(text=t(lang, "menu_analytics"), callback_data="analytics")],
            [InlineKeyboardButton(text=t(lang, "menu_manage_products"), callback_data="manage_products")],
            [InlineKeyboardButton(text=t(lang, "menu_registration_settings"), callback_data="registration_settings")]
        ])
    
    # Добавляем кнопки флориста
    if role in ["florist", "owner"]:
        kb_rows.append([InlineKeyboardButton(text=t(lang, "menu_manage_orders"), callback_data="manage_orders")])
    
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)

def get_user_lang(user: User) -> str:
    """Получить язык пользователя"""
    return user.lang or "ru"

async def format_product_name(product, lang: str) -> str:
    """Форматировать название товара по языку"""
    return product.name_ru if lang == "ru" else product.name_uz

async def format_product_description(product, lang: str) -> str:
    """Форматировать описание товара по языку"""
    return (product.desc_ru if lang == "ru" else product.desc_uz) or ""