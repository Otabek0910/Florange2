# tests/test_db_simple.py - создать в папке tests
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import asyncpg
from app.config import config

async def test_connection():
    """Простой тест подключения"""
    print(f"🔗 Тестируем: {config.DATABASE_URL}")
    
    try:
        # Извлекаем параметры из URL
        url = config.DATABASE_URL
        # postgresql+asyncpg://postgres:123@localhost:5432/florange
        
        if "postgresql+asyncpg://" in url:
            url = url.replace("postgresql+asyncpg://", "postgresql://")
        
        print(f"📡 Подключение к: {url}")
        
        # Прямое подключение через asyncpg
        conn = await asyncpg.connect(url)
        print("✅ Подключение успешно")
        
        # Тест запроса
        version = await conn.fetchval("SELECT version()")
        print(f"📊 PostgreSQL: {version.split()[1]}")
        
        await conn.close()
        print("🔌 Соединение закрыто")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print(f"💡 Проверьте:")
        print("  1. Запущен ли PostgreSQL")
        print("  2. Существует ли база florange")
        print("  3. Правильные ли креды в .env.development")

if __name__ == "__main__":
    asyncio.run(test_connection())

# Действия:
# 1. Создать tests/test_db_simple.py
# 2. Запустить: python tests/test_db_simple.py
# 3. Проверить что PostgreSQL запущен
# 4. Убедиться что база florange создана