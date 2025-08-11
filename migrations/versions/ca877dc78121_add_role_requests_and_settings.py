# Создать новую миграцию: alembic revision -m "add_role_requests_and_settings"

"""add role requests and settings

Revision ID: <новый_id>
Revises: 99adfde0087d
Create Date: 2025-08-11 XX:XX:XX

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '<новый_id>'
down_revision: Union[str, Sequence[str], None] = '99adfde0087d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Создаем таблицу настроек
    op.create_table('settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    
    # Создаем таблицу заявок на роли
    op.create_table('role_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('requested_role', sa.Enum('florist', 'owner', name='requestedroleenum'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='requeststatusenum'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Добавляем дефолтные настройки
    op.execute("""
        INSERT INTO settings (key, value, created_at) VALUES 
        ('florist_registration_open', 'false', NOW()),
        ('owner_registration_open', 'false', NOW())
    """)

def downgrade() -> None:
    op.drop_table('role_requests')
    op.drop_table('settings')
    op.execute("DROP TYPE IF EXISTS requestedroleenum")
    op.execute("DROP TYPE IF EXISTS requeststatusenum")