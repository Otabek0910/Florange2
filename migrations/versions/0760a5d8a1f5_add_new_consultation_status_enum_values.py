"""add new consultation status enum values

Revision ID: 0760a5d8a1f5
Revises: 2e3a6f4f74bc
Create Date: 2025-08-19 18:00:12.210574

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0760a5d8a1f5'
down_revision: Union[str, Sequence[str], None] = '2e3a6f4f74bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
     op.execute("ALTER TYPE consultationstatusenum ADD VALUE IF NOT EXISTS 'completed'")
     op.execute("ALTER TYPE consultationstatusenum ADD VALUE IF NOT EXISTS 'expired'")  
     op.execute("ALTER TYPE consultationstatusenum ADD VALUE IF NOT EXISTS 'declined'")

def downgrade():
     # PostgreSQL не поддерживает удаление enum значений
    pass

