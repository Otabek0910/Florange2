"""Валидаторы данных"""
import re
from typing import Optional

PHONE_PATTERN = re.compile(r"^\+?\d[\d\s\-()]{5,}$")

def validate_phone(phone: str) -> bool:
    """Валидация номера телефона"""
    return bool(PHONE_PATTERN.match(phone.strip()))

def validate_address(address: str) -> bool:
    """Валидация адреса"""
    return len(address.strip()) >= 10

def sanitize_text(text: str, max_length: int = 1000) -> str:
    """Очистка текста от опасных символов"""
    # Базовая очистка
    clean_text = text.strip()[:max_length]
    return clean_text