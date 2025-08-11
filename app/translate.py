# -*- coding: utf-8 -*-
from typing import Dict

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # Общие
    "start_choose_lang": {
        "ru": "Выберите язык:",
        "uz": "Tilni tanlang:"
    },
    "lang_saved_ru": {
        "ru": "Язык сохранён: Русский 🇷🇺",
        "uz": "Til saqlandi: Rus tili 🇷🇺"
    },
    "lang_saved_uz": {
        "ru": "Язык сохранён: Узбекский 🇺🇿",
        "uz": "Til saqlandi: Oʻzbek tili 🇺🇿"
    },
    "menu_title": {
        "ru": "Выберите действие:",
        "uz": "Amalni tanlang:"
    },
    "menu_catalog": {
        "ru": "🛍 Каталог",
        "uz": "🛍 Katalog"
    },
    "menu_cart": {
        "ru": "🛒 Корзина",
        "uz": "🛒 Savat"
    },
    "menu_orders": {
        "ru": "📦 Мои заказы",
        "uz": "📦 Buyurtmalarim"
    },

    # Каталог
    "no_categories": {
        "ru": "Категорий пока нет.",
        "uz": "Hozircha kategoriyalar yoʻq."
    },
    "choose_category": {
        "ru": "Выберите категорию:",
        "uz": "Kategoriyani tanlang:"
    },
    "no_products": {
        "ru": "В этой категории пока нет товаров.",
        "uz": "Bu kategoriyada hozircha mahsulot yoʻq."
    },
    "add_to_cart": {
        "ru": "Добавить в корзину 🛒",
        "uz": "Savatga qoʻshish 🛒"
    },
    "product_card_caption": {
        # {name} {desc} {price} {currency}
        "ru": "<b>{name}</b>\n\n{desc}\nЦена: {price} {currency}",
        "uz": "<b>{name}</b>\n\n{desc}\nNarxi: {price} {currency}"
    },

    # Корзина
    "cart_empty": {
        "ru": "Ваша корзина пуста.",
        "uz": "Savat bo‘sh."
    },
    "cart_title": {
        "ru": "🛒 Ваша корзина:",
        "uz": "🛒 Savatingiz:"
    },
    "cart_clear": {
        "ru": "❌ Очистить",
        "uz": "❌ Tozalash"
    },
    "cart_checkout": {
        "ru": "✅ Оформить заказ",
        "uz": "✅ Buyurtma berish"
    },
    "cart_cleared": {
        "ru": "Корзина очищена 🗑",
        "uz": "Savat tozalandi 🗑"
    },
    "item_added": {
        "ru": "Товар добавлен в корзину ✅",
        "uz": "Mahsulot savatga qoʻshildi ✅"
    },
    "total_line": {
        # {total} {currency}
        "ru": "\n<b>Итого:</b> {total} {currency}",
        "uz": "\n<b>Jami:</b> {total} {currency}"
    },

    # Валюта
    "currency": {
        "ru": "сум",
        "uz": "soʻm"
    },

        "ask_address": {
        "ru": "Введите адрес доставки (улица, дом, подъезд):",
        "uz": "Yetkazib berish manzilini kiriting (ko‘cha, uy, подъезд):"
    },
    "ask_phone": {
        "ru": "Введите контактный телефон (например, +99890XXXXXXX):",
        "uz": "Aloqa telefon raqamini kiriting (masalan, +99890XXXXXXX):"
    },
    "invalid_phone": {
        "ru": "Неверный формат телефона. Повторите ещё раз:",
        "uz": "Telefon formati noto‘g‘ri. Qayta kiriting:"
    },
    "ask_datetime": {
        "ru": "Когда доставить? Укажите дату/время (например, сегодня 18:00):",
        "uz": "Qachon yetkazamiz? Sana/vaqt kiriting (masalan, bugun 18:00):"
    },
    "confirm_order": {
        "ru": "Подтвердите заказ:",
        "uz": "Buyurtmani tasdiqlang:"
    },
    "order_created": {
        "ru": "Спасибо! Заказ создан. Мы свяжемся с вами для подтверждения ✅",
        "uz": "Rahmat! Buyurtma yaratildi. Tez orada bog‘lanamiz ✅"
    },


}

def t(lang: str, key: str, **kwargs) -> str:
    """
    Безопасный доступ к переводу.
    - lang: 'ru' | 'uz' (иначе fallback на 'ru')
    - key: ключ из TRANSLATIONS
    - kwargs: подстановки в шаблон (format)
    """
    lang = lang if lang in ("ru", "uz") else "ru"
    entry = TRANSLATIONS.get(key, {})
    template = entry.get(lang) or entry.get("ru") or key
    try:
        return template.format(**kwargs)
    except Exception:
        # если не хватает плейсхолдеров — вернём как есть
        return template
