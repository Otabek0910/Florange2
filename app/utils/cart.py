import redis
import json
from typing import Dict, Optional
from app.config import settings

# Подключение к Redis
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

def add_to_cart(user_id: int, product_id: int, qty: int = 1) -> None:
    """Добавить товар в корзину"""
    key = f"cart:{user_id}"
    current = redis_client.hget(key, str(product_id))
    current_qty = int(current) if current else 0
    new_qty = current_qty + qty
    
    redis_client.hset(key, str(product_id), new_qty)
    redis_client.expire(key, 900)  # TTL 15 минут

def get_cart(user_id: int) -> Dict[str, int]:
    """Получить корзину пользователя"""
    key = f"cart:{user_id}"
    cart_data = redis_client.hgetall(key)
    return {pid: int(qty) for pid, qty in cart_data.items()} if cart_data else {}

def clear_cart(user_id: int) -> None:
    """Очистить корзину"""
    key = f"cart:{user_id}"
    redis_client.delete(key)

def remove_from_cart(user_id: int, product_id: int, qty: int = 1) -> None:
    """Убрать товар из корзины"""
    key = f"cart:{user_id}"
    current = redis_client.hget(key, str(product_id))
    if not current:
        return
    
    current_qty = int(current)
    new_qty = max(0, current_qty - qty)
    
    if new_qty == 0:
        redis_client.hdel(key, str(product_id))
    else:
        redis_client.hset(key, str(product_id), new_qty)