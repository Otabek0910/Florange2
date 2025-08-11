# /project/app/translate.py

translate = {
    "start_message": {
        "ru": "Добро пожаловать в Florange 🌸\nВыберите язык:",
        "uz": "Florange ga xush kelibsiz 🌸\nTilni tanlang:"
    },
    "menu_main": {
        "ru": "Главное меню",
        "uz": "Asosiy menyu"
    },
    "menu_flowers": {
        "ru": "Цветы",
        "uz": "Gullar"
    },
    "menu_bouquets": {
        "ru": "Готовые композиции",
        "uz": "Tayyor kompozitsiyalar"
    },
    "menu_vip": {
        "ru": "VIP",
        "uz": "VIP"
    },
    "menu_cards": {
        "ru": "Открытки",
        "uz": "Ochiqchalar"
    },
    "menu_wrapping": {
        "ru": "Упаковка",
        "uz": "O‘rash"
    },
    "menu_plants": {
        "ru": "Комнатные растения",
        "uz": "Xonaki o‘simliklar"
    },
    "menu_toys_perfume": {
        "ru": "Игрушки и духи",
        "uz": "O‘yinchoqlar va atirlar"
    },
    "back": {
        "ru": "⬅️ Назад",
        "uz": "⬅️ Orqaga"
    }
}

def t(key: str, lang: str) -> str:
    """Возвращает перевод по ключу и языку"""
    if key not in translate:
        return key  # если ключ не найден, возвращаем сам ключ
    return translate[key].get(lang, translate[key].get("ru", key))
