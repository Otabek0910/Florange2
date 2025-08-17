"""create_consultation_buffer_table

Revision ID: 5f597ee6151c
Revises: 812c6f5922a0
Create Date: 2025-08-17 18:03:05.047047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f597ee6151c'
down_revision: Union[str, Sequence[str], None] = '812c6f5922a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создать таблицу буфера консультаций"""
    
    # Создаем таблицу буфера сообщений
    op.create_table(
        'consultation_buffer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('consultation_id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=True),
        sa.Column('photo_file_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Создаем индексы для быстрого поиска
    op.create_index('idx_consultation_buffer_consultation', 'consultation_buffer', ['consultation_id'])
    op.create_index('idx_consultation_buffer_created', 'consultation_buffer', ['created_at'])

def downgrade() -> None:
    """Удалить таблицу буфера консультаций"""
    op.drop_index('idx_consultation_buffer_created', 'consultation_buffer')
    op.drop_index('idx_consultation_buffer_consultation', 'consultation_buffer')
    op.drop_table('consultation_buffer')