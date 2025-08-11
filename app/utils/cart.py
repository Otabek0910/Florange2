"""Управление корзиной в Redis"""
import redis
import json
from typing import Dict, Optional
from app.config import settings

class CartManager:
    """Менеджер корзины"""
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    def _get_cart_key(self, user_id: int) -> str:
        """Получить ключ корзины для пользователя"""
        return f"cart:{user_id}"
    
    def add_to_cart(self, user_id: int, product_id: int, qty: int = 1) -> None:
        """Добавить товар в корзину"""
        key = self._get_cart_key(user_id)
        current = self.redis_client.hget(key, str(product_id))
        current_qty = int(current) if current else 0
        new_qty = current_qty + qty
        
        self.redis_client.hset(key, str(product_id), new_qty)
        self.redis_client.expire(key, 900)  # TTL 15 минут
    
    def get_cart(self, user_id: int) -> Dict[str, int]:
        """Получить корзину пользователя"""
        key = self._get_cart_key(user_id)
        cart_data = self.redis_client.hgetall(key)
        return {pid: int(qty) for pid, qty in cart_data.items()} if cart_data else {}
    
    def remove_from_cart(self, user_id: int, product_id: int, qty: int = 1) -> None:
        """Убрать товар из корзины"""
        key = self._get_cart_key(user_id)
        current = self.redis_client.hget(key, str(product_id))
        if not current:
            return
        
        current_qty = int(current)
        new_qty = max(0, current_qty - qty)
        
        if new_qty == 0:
            self.redis_client.hdel(key, str(product_id))
        else:
            self.redis_client.hset(key, str(product_id), new_qty)
    
    def clear_cart(self, user_id: int) -> None:
        """Очистить корзину"""
        key = self._get_cart_key(user_id)
        self.redis_client.delete(key)
    
    def get_cart_total(self, user_id: int) -> int:
        """Получить общее количество товаров в корзине"""
        cart = self.get_cart(user_id)
        return sum(cart.values())

# Backward compatibility
cart_manager = CartManager()

def add_to_cart(user_id: int, product_id: int, qty: int = 1) -> None:
    cart_manager.add_to_cart(user_id, product_id, qty)

def get_cart(user_id: int) -> Dict[str, int]:
    return cart_manager.get_cart(user_id)

def clear_cart(user_id: int) -> None:
    cart_manager.clear_cart(user_id)

def remove_from_cart(user_id: int, product_id: int, qty: int = 1) -> None:
    cart_manager.remove_from_cart(user_id, product_id, qty)