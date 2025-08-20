# check_db_structure.py — создать в корне проекта

import asyncio
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Проверяем переменные окружения
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASS', '1234') 
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'Florange')

print(f"🔧 Подключение к БД:")
print(f"   Host: {DB_HOST}:{DB_PORT}")
print(f"   Database: {DB_NAME}")
print(f"   User: {DB_USER}")
print("-" * 50)

DB_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def check_consultations_table():
    """Проверить структуру таблицы consultations"""
    
    engine = create_engine(DB_URL)
    
    with engine.connect() as conn:
        # Проверяем столбцы таблицы consultations
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'consultations'
            ORDER BY ordinal_position;
        """))
        
        print("📋 Структура таблицы consultations:")
        print("-" * 50)
        
        columns = result.fetchall()
        for col in columns:
            print(f"• {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
        
        # Проверяем индексы
        print("\n📂 Индексы:")
        print("-" * 50)
        
        idx_result = conn.execute(text("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'consultations';
        """))
        
        indexes = idx_result.fetchall()
        for idx in indexes:
            print(f"• {idx[0]}: {idx[1]}")
        
        # Проверяем enum значения
        print("\n🏷️  Enum значения ConsultationStatusEnum:")
        print("-" * 50)
        
        enum_result = conn.execute(text("""
            SELECT enumlabel 
            FROM pg_enum 
            WHERE enumtypid = (
                SELECT oid 
                FROM pg_type 
                WHERE typname = 'consultationstatusenum'
            );
        """))
        
        enum_values = enum_result.fetchall()
        for val in enum_values:
            print(f"• {val[0]}")

if __name__ == "__main__":
    check_consultations_table()