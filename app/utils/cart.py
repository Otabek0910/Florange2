# app/utils/cart.py - полная замена на async Redis
import asyncio
import json
from typing import Dict, List, Optional
import redis.asyncio as redis

class CartManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.use_redis = True
        self.memory_cache = {}  # Fallback storage
        self._redis_client = None
        
    async def _get_redis_client(self):
        """Получить или создать async Redis клиент"""
        if not self._redis_client:
            try:
                self._redis_client = redis.from_url(
                    self.redis_url, 
                    decode_responses=True,
                    socket_keepalive=True,
                    socket_keepalive_options={}
                )
                # Проверяем подключение
                await self._redis_client.ping()
                print("✅ Redis подключен (async)")
                self.use_redis = True
            except Exception as e:
                print(f"⚠️ Redis недоступен: {e}")
                print("🔄 Переключаюсь на память")
                self.use_redis = False
                self._redis_client = None
        return self._redis_client

    async def get_cart(self, user_id: int) -> Dict:
        """Получить корзину пользователя"""
        try:
            if self.use_redis:
                redis_client = await self._get_redis_client()
                if redis_client:
                    key = f"cart:{user_id}"
                    cart_data = await redis_client.hgetall(key)
                    return {int(k): int(v) for k, v in cart_data.items()} if cart_data else {}
            
            return self.memory_cache.get(user_id, {})
        except Exception as e:
            print(f"Cart get error: {e}")
            return self.memory_cache.get(user_id, {})

    async def add_to_cart(self, user_id: int, product_id: int, quantity: int = 1):
        """Добавить товар в корзину"""
        try:
            if self.use_redis:
                redis_client = await self._get_redis_client()
                if redis_client:
                    key = f"cart:{user_id}"
                    await redis_client.hincrby(key, product_id, quantity)
                    await redis_client.expire(key, 86400)  # 24 часа
                    return
            
            # Fallback to memory
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

    async def remove_from_cart(self, user_id: int, product_id: int):
        """Удалить товар из корзины"""
        try:
            if self.use_redis:
                redis_client = await self._get_redis_client()
                if redis_client:
                    key = f"cart:{user_id}"
                    await redis_client.hdel(key, product_id)
                    return
            
            if user_id in self.memory_cache:
                self.memory_cache[user_id].pop(product_id, None)
        except Exception as e:
            print(f"Cart remove error: {e}")

    async def clear_cart(self, user_id: int):
        """Очистить корзину"""
        try:
            if self.use_redis:
                redis_client = await self._get_redis_client()
                if redis_client:
                    key = f"cart:{user_id}"
                    await redis_client.delete(key)
                    return
            
            self.memory_cache.pop(user_id, None)
        except Exception as e:
            print(f"Cart clear error: {e}")

    async def close(self):
        """Закрыть соединение с Redis"""
        if self._redis_client:
            try:
                await self._redis_client.aclose()
                print("✅ Redis соединение закрыто")
            except Exception as e:
                print(f"Redis close error: {e}")
            finally:
                self._redis_client = None

# Глобальный экземпляр
cart_manager = CartManager()

# Синхронные обертки для совместимости (НЕ РЕКОМЕНДУЕТСЯ)
def get_cart(user_id: int) -> Dict:
    """DEPRECATED: Используйте await cart_manager.get_cart()"""
    try:
        return asyncio.run(cart_manager.get_cart(user_id))
    except RuntimeError:
        # Если уже в event loop, используем память
        return cart_manager.memory_cache.get(user_id, {})

def add_to_cart(user_id: int, product_id: int, quantity: int = 1):
    """DEPRECATED: Используйте await cart_manager.add_to_cart()"""
    try:
        return asyncio.run(cart_manager.add_to_cart(user_id, product_id, quantity))
    except RuntimeError:
        # Fallback to memory
        if user_id not in cart_manager.memory_cache:
            cart_manager.memory_cache[user_id] = {}
        current = cart_manager.memory_cache[user_id].get(product_id, 0)
        cart_manager.memory_cache[user_id][product_id] = current + quantity

def remove_from_cart(user_id: int, product_id: int):
    """DEPRECATED: Используйте await cart_manager.remove_from_cart()"""
    try:
        return asyncio.run(cart_manager.remove_from_cart(user_id, product_id))
    except RuntimeError:
        if user_id in cart_manager.memory_cache:
            cart_manager.memory_cache[user_id].pop(product_id, None)

def clear_cart(user_id: int):
    """DEPRECATED: Используйте await cart_manager.clear_cart()"""
    try:
        return asyncio.run(cart_manager.clear_cart(user_id))
    except RuntimeError:
        cart_manager.memory_cache.pop(user_id, None)