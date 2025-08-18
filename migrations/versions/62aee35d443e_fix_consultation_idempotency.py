"""fix_consultation_idempotency

Revision ID: 62aee35d443e
Revises: 975786b7d89a
Create Date: 2025-08-18 15:06:24.573467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62aee35d443e'
down_revision: Union[str, Sequence[str], None] = '975786b7d89a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Исправление консультаций: идемпотентность + защита от гонок"""
    
    # 1. Добавляем новые поля для идемпотентности
    print("🔧 Добавляем поля request_key и expires_at...")
    op.add_column('consultations', sa.Column('request_key', sa.String(100), nullable=True))
    op.add_column('consultations', sa.Column('expires_at', sa.DateTime(), nullable=True))
    
    # 2. Добавляем поле для улучшенного статуса
    print("🔧 Добавляем enum 'expired' в ConsultationStatusEnum...")
    # Добавляем новое значение в enum
    op.execute("ALTER TYPE consultationstatusenum ADD VALUE IF NOT EXISTS 'expired'")
    
    # 3. Создаём уникальные индексы для предотвращения дублей
    print("🔧 Создаём уникальные индексы...")
    
    # Уникальный индекс для request_key (идемпотентность)
    op.create_index(
        'idx_consultations_request_key_unique', 
        'consultations', 
        ['request_key'],
        unique=True,
        postgresql_where="request_key IS NOT NULL"
    )
    
    # Уникальный индекс: один клиент = одна активная/pending консультация
    op.create_index(
        'idx_consultations_active_client_unique',
        'consultations',
        ['client_id'],
        unique=True,
        postgresql_where="status IN ('active', 'pending')"
    )
    
    # 4. Индексы для производительности
    print("🔧 Создаём индексы для производительности...")
    
    # Индекс для быстрого поиска занятых флористов
    op.create_index(
        'idx_consultations_florist_status',
        'consultations',
        ['florist_id', 'status'],
        postgresql_where="status IN ('active', 'pending')"
    )
    
    # Индекс для поиска истёкших консультаций
    op.create_index(
        'idx_consultations_expires_at',
        'consultations',
        ['expires_at'],
        postgresql_where="expires_at IS NOT NULL AND status = 'pending'"
    )
    
    # 5. Заполняем expires_at для существующих pending консультаций
    print("🔧 Обновляем существующие pending консультации...")
    op.execute("""
        UPDATE consultations 
        SET expires_at = created_at + INTERVAL '15 minutes'
        WHERE status = 'pending' AND expires_at IS NULL
    """)
    
    # 6. Создаём функцию для автоматической очистки истёкших консультаций
    print("🔧 Создаём функцию cleanup_expired_consultations...")
    op.execute("""
        CREATE OR REPLACE FUNCTION cleanup_expired_consultations() 
        RETURNS INTEGER AS $$
        DECLARE
            updated_count INTEGER;
        BEGIN
            UPDATE consultations 
            SET status = 'expired'::consultationstatusenum
            WHERE status = 'pending'::consultationstatusenum 
            AND expires_at < NOW();
            
            GET DIAGNOSTICS updated_count = ROW_COUNT;
            
            -- Логируем результат
            IF updated_count > 0 THEN
                RAISE NOTICE 'Expired % consultations', updated_count;
            END IF;
            
            RETURN updated_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    print("✅ Миграция консультаций успешно применена!")


def downgrade() -> None:
    """Откат изменений (обратная миграция)"""
    
    print("⏪ Откатываем изменения консультаций...")
    
    # 1. Удаляем функцию
    op.execute("DROP FUNCTION IF EXISTS cleanup_expired_consultations()")
    
    # 2. Удаляем индексы
    op.drop_index('idx_consultations_expires_at', table_name='consultations')
    op.drop_index('idx_consultations_florist_status', table_name='consultations')
    op.drop_index('idx_consultations_active_client_unique', table_name='consultations')
    op.drop_index('idx_consultations_request_key_unique', table_name='consultations')
    
    # 3. Удаляем колонки
    op.drop_column('consultations', 'expires_at')
    op.drop_column('consultations', 'request_key')
    
    # Примечание: enum 'expired' оставляем, так как его удаление сложнее
    # и может сломать существующие данные
    
    print("✅ Откат завершён!")