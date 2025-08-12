"""add_consultations_system

Revision ID: f85d9438e057
Revises: 01a99a62f295
Create Date: 2025-08-12 03:08:28.486772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f85d9438e057'
down_revision: Union[str, Sequence[str], None] = '01a99a62f295'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add theme and archive_id fields to consultations table."""
    op.add_column('consultations', sa.Column('theme', sa.String(length=255), nullable=True))
    op.add_column('consultations', sa.Column('archive_id', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Remove theme and archive_id fields from consultations table."""
    op.drop_column('consultations', 'archive_id')
    op.drop_column('consultations', 'theme')