"""add_created_at_to_consultation_messages

Revision ID: 975786b7d89a
Revises: 5f597ee6151c
Create Date: 2025-08-18 10:40:44.402849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '975786b7d89a'
down_revision: Union[str, Sequence[str], None] = '5f597ee6151c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Добавляем поле created_at
    op.add_column('consultation_messages', 
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )
    
    # Заполняем created_at из sent_at
    op.execute("UPDATE consultation_messages SET created_at = sent_at WHERE created_at IS NULL")
    
    # Делаем поле обязательным
    op.alter_column('consultation_messages', 'created_at', nullable=False)

def downgrade():
    op.drop_column('consultation_messages', 'created_at')
