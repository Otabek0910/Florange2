"""add_new_consultation_statuses

Revision ID: 0fbf9f2170bc
Revises: d8bc4b6382fc
Create Date: 2025-08-17 17:01:21.998153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fbf9f2170bc'
down_revision: Union[str, Sequence[str], None] = 'd8bc4b6382fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавить новые значения в enum"""
    
    # Добавляем новые значения в enum по одному
    op.execute("ALTER TYPE consultationstatusenum ADD VALUE 'pending'")
    op.execute("ALTER TYPE consultationstatusenum ADD VALUE 'timeout_no_response'") 
    op.execute("ALTER TYPE consultationstatusenum ADD VALUE 'force_closed'")

def downgrade() -> None:
    """Откат невозможен для PostgreSQL enum values"""
    # PostgreSQL не поддерживает удаление значений из enum
    # Нужно пересоздавать весь enum, что слишком опасно
    pass