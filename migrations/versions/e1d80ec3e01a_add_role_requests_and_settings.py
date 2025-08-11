"""add role requests and settings

Revision ID: e1d80ec3e01a
Revises: 99adfde0087d
Create Date: 2025-08-11 12:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e1d80ec3e01a'
down_revision: Union[str, Sequence[str], None] = '99adfde0087d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Создаем enum типы ТОЛЬКО если они не существуют
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE requestedroleenum AS ENUM ('florist', 'owner');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE requeststatusenum AS ENUM ('pending', 'approved', 'rejected');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Создаем таблицу настроек ТОЛЬКО если не существует
    op.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id SERIAL PRIMARY KEY,
            key VARCHAR(100) UNIQUE NOT NULL,
            value VARCHAR(500) NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    
    # Создаем таблицу заявок на роли ТОЛЬКО если не существует
    op.execute("""
        CREATE TABLE IF NOT EXISTS role_requests (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            requested_role requestedroleenum NOT NULL,
            status requeststatusenum NOT NULL DEFAULT 'pending',
            reason TEXT,
            approved_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    
    # Добавляем дефолтные настройки ТОЛЬКО если их нет
    op.execute("""
        INSERT INTO settings (key, value, created_at) 
        SELECT 'florist_registration_open', 'false', NOW()
        WHERE NOT EXISTS (SELECT 1 FROM settings WHERE key = 'florist_registration_open');
        
        INSERT INTO settings (key, value, created_at) 
        SELECT 'owner_registration_open', 'false', NOW()
        WHERE NOT EXISTS (SELECT 1 FROM settings WHERE key = 'owner_registration_open');
    """)

def downgrade() -> None:
    op.drop_table('role_requests')
    op.drop_table('settings')
    op.execute("DROP TYPE IF EXISTS requestedroleenum")
    op.execute("DROP TYPE IF EXISTS requeststatusenum")