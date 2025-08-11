"""add_last_name_to_users

Revision ID: 3e17caacd615
Revises: e1d80ec3e01a
Create Date: 2025-08-12 02:03:57.553364

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e17caacd615'
down_revision: Union[str, Sequence[str], None] = 'e1d80ec3e01a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_name', sa.String(length=100), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'last_name')
