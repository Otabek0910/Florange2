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

    "my_orders_title": {
    "ru": "📦 Ваши заказы:",
    "uz": "📦 Sizning buyurtmalaringiz:"
    },
    "no_orders": {
        "ru": "У вас пока нет заказов.",
        "uz": "Sizda hali buyurtmalar yo'q."
    },
    "back_to_menu": {
        "ru": "↩️ В меню",
        "uz": "↩️ Menyuga"
    },
    "order_status_new": {
        "ru": "🆕 Новый",
        "uz": "🆕 Yangi"
    },
    "order_status_delivered": {
        "ru": "✅ Доставлен",
        "uz": "✅ Yetkazildi"
    },
    "user_not_found": {
        "ru": "Пользователь не найден. Нажмите /start",
        "uz": "Foydalanuvchi topilmadi. /start bosing"
    },

    # Система заявок на роли
    "choose_role_client_only": {
        "ru": "Регистрация флористов и владельцев временно закрыта. Вы можете зарегистрироваться только как клиент:",
        "uz": "Florist va egalar ro'yxatdan o'tishi vaqtincha yopiq. Siz faqat mijoz sifatida ro'yxatdan o'tishingiz mumkin:"
    },
    "request_role_reason": {
        "ru": "Вы подаете заявку на роль {role}. Укажите причину вашего запроса:",
        "uz": "{role} roli uchun ariza topshiryapsiz. So'rovingizning sababini ko'rsating:"
    },
    "role_request_submitted": {
        "ru": "Ваша заявка на роль {role} отправлена администратору. Ожидайте подтверждения.",
        "uz": "{role} roli uchun arizangiz administratorga yuborildi. Tasdiqlanishini kuting."
    },
    "role_approved": {
        "ru": "🎉 Ваша заявка на роль {role} одобрена! Теперь вам доступны новые функции.",
        "uz": "🎉 {role} roli uchun arizangiz tasdiqlandi! Endi sizga yangi funksiyalar mavjud."
    },
    "role_rejected": {
        "ru": "😔 Ваша заявка на роль {role} отклонена администратором.",
        "uz": "😔 {role} roli uchun arizangiz administrator tomonidan rad etildi."
    },

    # Админ-панель
    "access_denied": {
        "ru": "У вас нет доступа к этой функции.",
        "uz": "Sizda bu funksiyaga kirish huquqi yo'q."
    },
    "request_not_found": {
        "ru": "Заявка не найдена или уже обработана.",
        "uz": "Ariza topilmadi yoki allaqachon ko'rib chiqilgan."
    },
    "request_approved": {
        "ru": "Заявка одобрена ✅",
        "uz": "Ariza tasdiqlandi ✅"
    },
    "request_rejected": {
        "ru": "Заявка отклонена ❌",
        "uz": "Ariza rad etildi ❌"
    },
    "registration_settings": {
        "ru": "⚙️ Настройки регистрации\n\nФлористы: {florist_status}\nВладельцы: {owner_status}",
        "uz": "⚙️ Ro'yxatdan o'tish sozlamalari\n\nFloristlar: {florist_status}\nEgalar: {owner_status}"
    },
    "open_florist_reg": {
        "ru": "🟢 Открыть регистрацию флористов",
        "uz": "🟢 Floristlar ro'yxatdan o'tishini ochish"
    },
    "close_florist_reg": {
        "ru": "🔴 Закрыть регистрацию флористов",
        "uz": "🔴 Floristlar ro'yxatdan o'tishini yopish"
    },
    "open_owner_reg": {
        "ru": "🟢 Открыть регистрацию владельцев",
        "uz": "🟢 Egalar ro'yxatdan o'tishini ochish"
    },
    "close_owner_reg": {
        "ru": "🔴 Закрыть регистрацию владельцев",
        "uz": "🔴 Egalar ro'yxatdan o'tishini yopish"
    },
    "open": {
        "ru": "Открыта",
        "uz": "Ochiq"
    },
    "closed": {
        "ru": "Закрыта",
        "uz": "Yopiq"
    },
    "opened": {
        "ru": "открыта",
        "uz": "ochildi"
    },
    "florist_registration_toggled": {
        "ru": "Регистрация флористов {status}",
        "uz": "Floristlar ro'yxatdan o'tishi {status}"
    },
    "owner_registration_toggled": {
        "ru": "Регистрация владельцев {status}",
        "uz": "Egalar ro'yxatdan o'tishi {status}"
    },

    # Дополнительные меню для владельца
    "menu_manage_registration": {
        "ru": "⚙️ Управление регистрацией",
        "uz": "⚙️ Ro'yxatdan o'tishni boshqarish"
    },
    "menu_pending_requests": {
        "ru": "📋 Заявки на роли",
        "uz": "📋 Rol uchun arizalar"
    },

    # Добавить в конец файла переводы для статусов
    "no_pending_requests": {
        "ru": "Нет ожидающих заявок.",
        "uz": "Kutilayotgan arizalar yo'q."
    },
    "pending_requests_title": {
        "ru": "📋 Ожидающие заявки:",
        "uz": "📋 Kutilayotgan arizalar:"
    },
    "request_status_pending": {
        "ru": "⏳ Ожидает",
        "uz": "⏳ Kutilmoqda"
    },
    "request_status_approved": {
        "ru": "✅ Одобрено",
        "uz": "✅ Tasdiqlangan"
    },
    "request_status_rejected": {
        "ru": "❌ Отклонено",
        "uz": "❌ Rad etilgan"
    },

       # === МЕНЮ ===
    "menu_analytics": {
        "ru": "📊 Аналитика", 
        "uz": "📊 Analitika"
    },
    "menu_manage_products": {
        "ru": "📦 Управление товарами",
        "uz": "📦 Mahsulotlarni boshqarish"
    },
    "menu_manage_orders": {
        "ru": "📋 Управление заказами", 
        "uz": "📋 Buyurtmalarni boshqarish"
    },
    "menu_registration_settings": {
        "ru": "⚙️ Настройки регистрации",
        "uz": "⚙️ Ro'yxatga olish sozlamalari"
    },

    # === РЕГИСТРАЦИЯ ===
    "registration_choose_role": {
        "ru": "Выберите вашу роль:",
        "uz": "Rolingizni tanlang:"
    },
    "role_client": {
        "ru": "👤 Клиент",
        "uz": "👤 Mijoz"
    },
    "role_florist": {
        "ru": "🌸 Флорист", 
        "uz": "🌸 Florist"
    },
    "role_owner": {
        "ru": "👑 Владелец",
        "uz": "👑 Egasi"
    },
    "registration_closed": {
        "ru": "❌ Регистрация флористов/владельцев временно закрыта",
        "uz": "❌ Florist/egalar ro'yxatga olish vaqtincha yopiq"
    },
    "ask_role_reason": {
        "ru": "Объясните, почему вы хотите получить эту роль:",
        "uz": "Nega bu rolni olishni xohlayotganingizni tushuntiring:"
    },
    "role_request_sent": {
        "ru": "✅ Заявка отправлена администратору",
        "uz": "✅ Ariza administratorga yuborildi"
    },

    # === НАСТРОЙКИ ===
    "settings_title": {
        "ru": "⚙️ Настройки регистрации:",
        "uz": "⚙️ Ro'yxatga olish sozlamalari:"
    },
    "florist_registration": {
        "ru": "🌸 Регистрация флористов:",
        "uz": "🌸 Floristlar ro'yxati:"
    },
    "owner_registration": {
        "ru": "👑 Регистрация владельцев:",
        "uz": "👑 Egalar ro'yxati:"
    },
    "status_open": {
        "ru": "🟢 Открыта",
        "uz": "🟢 Ochiq"
    },
    "status_closed": {
        "ru": "🔴 Закрыта", 
        "uz": "🔴 Yopiq"
    },
    "toggle_florist_reg": {
        "ru": "🔄 Переключить регистрацию флористов",
        "uz": "🔄 Florist ro'yxatini o'zgartirish"
    },
    "toggle_owner_reg": {
        "ru": "🔄 Переключить регистрацию владельцев",
        "uz": "🔄 Egalar ro'yxatini o'zgartirish"
    },

    # === КАТАЛОГ ===
    "back_to_categories": {
        "ru": "↩️ К категориям",
        "uz": "↩️ Kategoriyalarga"
    },
    "product_details": {
        "ru": "📝 Подробнее",
        "uz": "📝 Batafsil"
    },
    # === СИСТЕМНЫЕ ===
    "start_choose_lang": {
        "ru": "Выберите язык:",
        "uz": "Tilni tanlang:"
    },
    "menu_title": {
        "ru": "Выберите действие:",
        "uz": "Amalni tanlang:"
    },

        # === АДМИН ФУНКЦИИ ===
    "admin_menu": {
        "ru": "👑 Админ-меню",
        "uz": "👑 Admin-menyu" 
    },
    "back_to_admin": {
        "ru": "↩️ К админ-меню",
        "uz": "↩️ Admin-menyuga"
    },
    "start_choose_lang": {
        "ru": "Выберите язык:",
        "uz": "Tilni tanlang:"
    },
    "menu_title": {
        "ru": "Выберите действие:",
        "uz": "Amalni tanlang:"
    },

    "product_not_found": {
    "ru": "Товар не найден или недоступен",
    "uz": "Mahsulot topilmadi yoki mavjud emas"
    },
    "item_removed": {
        "ru": "Товар убран из корзины ✅",
        "uz": "Mahsulot savatdan olib tashlandi ✅"
    },

    "invalid_address": {
    "ru": "Адрес слишком короткий. Укажите подробный адрес (мин. 10 символов):",
    "uz": "Manzil juda qisqa. Batafsil manzil kiriting (kamida 10 ta belgi):"
    },
    "cart_has_invalid_items": {
        "ru": "В корзине есть недоступные товары. Обновите корзину и попробуйте снова.",
        "uz": "Savatda mavjud bo'lmagan mahsulotlar bor. Savatni yangilang va qayta urinib ko'ring."
    },
    "order_cancelled": {
        "ru": "Оформление заказа отменено",
        "uz": "Buyurtma berish bekor qilindi"
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
