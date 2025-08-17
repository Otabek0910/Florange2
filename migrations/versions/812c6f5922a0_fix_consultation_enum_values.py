"""fix_consultation_enum_values

Revision ID: 812c6f5922a0
Revises: a06c49e035f6
Create Date: 2025-08-17 17:12:27.413402

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '812c6f5922a0'
down_revision: Union[str, Sequence[str], None] = 'a06c49e035f6'
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
    pass