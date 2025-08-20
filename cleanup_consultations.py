# cleanup_consultations.py — создать в корне проекта

import asyncio
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

def cleanup_hanging_consultations():
    """Очистка зависших консультаций"""
    
    engine = create_engine(DB_URL)
    
    with engine.connect() as conn:
        # 1. Находим зависшие pending консультации (старше 15 минут)
        result = conn.execute(text("""
            UPDATE consultations 
            SET status = 'expired', completed_at = NOW()
            WHERE status = 'pending' 
            AND created_at < NOW() - INTERVAL '15 minutes'
            RETURNING id, client_id, florist_id;
        """))
        
        updated = result.fetchall()
        print(f"🧹 Cleaned up {len(updated)} expired pending consultations")
        
        # 2. Находим активные консультации без недавних сообщений (старше 2 часов)
        result2 = conn.execute(text("""
            UPDATE consultations 
            SET status = 'completed', completed_at = NOW()
            WHERE status = 'active' 
            AND started_at < NOW() - INTERVAL '2 hours'
            AND id NOT IN (
                SELECT DISTINCT consultation_id 
                FROM consultation_messages 
                WHERE created_at > NOW() - INTERVAL '30 minutes'
            )
            RETURNING id;
        """))
        
        auto_completed = result2.fetchall()
        print(f"🧹 Auto-completed {len(auto_completed)} stale active consultations")
        
        conn.commit()
        
        # 3. Показываем текущее состояние
        result3 = conn.execute(text("""
            SELECT status, COUNT(*) as count
            FROM consultations 
            GROUP BY status
            ORDER BY status;
        """))
        
        print("\n📊 Current consultation status:")
        for row in result3.fetchall():
            print(f"   {row[0]}: {row[1]}")

if __name__ == "__main__":
    cleanup_hanging_consultations()