"""cleanup_expired_consultations

Revision ID: abdd8fdf323b
Revises: 62aee35d443e
Create Date: 2025-08-18 17:43:22.733523

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abdd8fdf323b'
down_revision: Union[str, Sequence[str], None] = '62aee35d443e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.execute("""
    -- индекс на истечения (идемпотентно)
    CREATE INDEX IF NOT EXISTS idx_consultations_pending_expire
      ON consultations (expires_at) WHERE status = 'pending';

    -- СНАЧАЛА ДРОПНУТЬ (меняем тип возврата)
    DROP FUNCTION IF EXISTS cleanup_expired_consultations();

    -- СОЗДАТЬ ЗАНОВО: возвращаем строки (id, client_id, florist_id)
    CREATE FUNCTION cleanup_expired_consultations()
    RETURNS TABLE (id integer, client_id integer, florist_id integer)
    LANGUAGE plpgsql
    AS $$
    BEGIN
      RETURN QUERY
      UPDATE consultations
      SET status = 'expired',
          completed_at = NOW()
      WHERE status = 'pending'
        AND expires_at IS NOT NULL
        AND expires_at < NOW()
      RETURNING id, client_id, florist_id;
    END;
    $$;
    """)

def downgrade() -> None:
    op.execute("""
    DROP FUNCTION IF EXISTS cleanup_expired_consultations();
    DROP INDEX IF EXISTS idx_consultations_pending_expire;
    """)