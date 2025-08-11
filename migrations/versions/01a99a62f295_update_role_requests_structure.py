"""update_role_requests_structure

Revision ID: 01a99a62f295
Revises: 38de801a75a1
Create Date: 2025-08-12 02:33:35.445138

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '01a99a62f295'
down_revision: Union[str, Sequence[str], None] = '38de801a75a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем новые поля
    op.add_column('role_requests', sa.Column('user_tg_id', sa.String(length=50), nullable=True))
    op.add_column('role_requests', sa.Column('user_data', sa.Text(), nullable=True))
    
    # Делаем user_id nullable
    op.alter_column('role_requests', 'user_id', nullable=True)
    
    # Заполняем user_tg_id из существующих данных если есть
    op.execute("""
        UPDATE role_requests 
        SET user_tg_id = (SELECT tg_id FROM users WHERE users.id = role_requests.user_id)
        WHERE user_id IS NOT NULL
    """)

def downgrade() -> None:
    op.drop_column('role_requests', 'user_data')
    op.drop_column('role_requests', 'user_tg_id')
    op.alter_column('role_requests', 'user_id', nullable=False)