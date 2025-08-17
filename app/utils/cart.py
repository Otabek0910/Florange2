# app/utils/cart.py - ПОЛНАЯ ЗАМЕНА

import redis
import json
from typing import Dict, List, Optional

class CartManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.use_redis = True
        self.memory_cache = {}  # Fallback storage
        
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Проверяем подключение
            self.redis_client.ping()
            print("✅ Redis подключен")
        except Exception as e:
            print(f"⚠️ Redis недоступен: {e}")
            print("🔄 Переключаюсь на память (данные не сохраняются между перезапусками)")
            self.use_redis = False

    def get_cart(self, user_id: int) -> Dict:
        """Получить корзину пользователя"""
        try:
            if self.use_redis:
                key = f"cart:{user_id}"
                cart_data = self.redis_client.hgetall(key)
                return {int(k): int(v) for k, v in cart_data.items()}
            else:
                return self.memory_cache.get(user_id, {})
        except Exception as e:
            print(f"Cart get error: {e}")
            return self.memory_cache.get(user_id, {})

    def add_to_cart(self, user_id: int, product_id: int, quantity: int = 1):
        """Добавить товар в корзину"""
        try:
            if self.use_redis:
                key = f"cart:{user_id}"
                self.redis_client.hincrby(key, product_id, quantity)
                self.redis_client.expire(key, 86400)  # 24 часа
            else:
                if user_id not in self.memory_cache:
                    self.memory_cache[user_id] = {}
                current = self.memory_cache[user_id].get(product_id, 0)
                self.memory_cache[user_id][product_id] = current + quantity
        except Exception as e:
            print(f"Cart add error: {e}")
            # Fallback to memory
            if user_id not in self.memory_cache:
                self.memory_cache[user_id] = {}
            current = self.memory_cache[user_id].get(product_id, 0)
            self.memory_cache[user_id][product_id] = current + quantity

    def remove_from_cart(self, user_id: int, product_id: int):
        """Удалить товар из корзины"""
        try:
            if self.use_redis:
                key = f"cart:{user_id}"
                self.redis_client.hdel(key, product_id)
            else:
                if user_id in self.memory_cache:
                    self.memory_cache[user_id].pop(product_id, None)
        except Exception as e:
            print(f"Cart remove error: {e}")

    def clear_cart(self, user_id: int):
        """Очистить корзину"""
        try:
            if self.use_redis:
                key = f"cart:{user_id}"
                self.redis_client.delete(key)
            else:
                self.memory_cache.pop(user_id, None)
        except Exception as e:
            print(f"Cart clear error: {e}")

# Глобальный экземпляр
cart_manager = CartManager()

# Вспомогательные функции (для совместимости)
def get_cart(user_id: int) -> Dict:
    return cart_manager.get_cart(user_id)

def add_to_cart(user_id: int, product_id: int, quantity: int = 1):
    return cart_manager.add_to_cart(user_id, product_id, quantity)

def remove_from_cart(user_id: int, product_id: int):
    return cart_manager.remove_from_cart(user_id, product_id)

def clear_cart(user_id: int):
    return cart_manager.clear_cart(user_id)