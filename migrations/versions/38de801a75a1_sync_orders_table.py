"""sync_orders_table

Revision ID: 38de801a75a1
Revises: 921d19c0dda7
Create Date: 2025-08-12 02:23:36.528415

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38de801a75a1'
down_revision: Union[str, Sequence[str], None] = '921d19c0dda7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Переименовываем total в total_price если нужно
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'orders' AND column_name = 'total'
            ) THEN
                ALTER TABLE orders RENAME COLUMN total TO total_price;
            END IF;
        END $$;
    """)
    
    # Добавляем phone если его нет
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'orders' AND column_name = 'phone'
            ) THEN
                ALTER TABLE orders ADD COLUMN phone VARCHAR(20);
            END IF;
        END $$;
    """)

def downgrade() -> None:
    op.execute("ALTER TABLE orders RENAME COLUMN total_price TO total")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS phone")
