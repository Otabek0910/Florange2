import asyncio
import os
from sqlalchemy import text
from dotenv import load_dotenv
from app.database import engine

load_dotenv()

async def load_seed_data():
    """Загрузить тестовые данные"""
    try:
        with open("seed_data.sql", "r", encoding="utf-8") as f:
            sql_content = f.read()
        
        async with engine.begin() as conn:
            # Разделить на отдельные команды
            commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip()]
            for command in commands:
                if command:  # Проверить что команда не пустая
                    await conn.execute(text(command))
        
        print("✅ Тестовые данные загружены")
    except FileNotFoundError:
        print("❌ Файл seed_data.sql не найден")
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")

if __name__ == "__main__":
    asyncio.run(load_seed_data())