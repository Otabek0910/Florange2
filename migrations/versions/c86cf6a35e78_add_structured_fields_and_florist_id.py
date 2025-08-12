"""add_structured_fields_and_florist_id

Revision ID: c86cf6a35e78
Revises: 726e61cee20b
Create Date: 2025-08-12 16:59:18.195616

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c86cf6a35e78'
down_revision: Union[str, Sequence[str], None] = '726e61cee20b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Минимальные безопасные улучшения."""
    
    # 1. Добавляем структурированные поля в role_requests
    op.add_column('role_requests', sa.Column('first_name', sa.String(length=100), nullable=True))
    op.add_column('role_requests', sa.Column('last_name', sa.String(length=100), nullable=True))
    op.add_column('role_requests', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('role_requests', sa.Column('lang', sa.String(length=5), nullable=True))
    
    # 2. Добавляем florist_id в orders (кто принял заказ)
    op.add_column('orders', sa.Column('florist_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_orders_florist', 'orders', 'users', ['florist_id'], ['id'])
    
    # 3. Добавляем полезные индексы
    op.create_index('idx_role_requests_status', 'role_requests', ['status'])
    op.create_index('idx_consultations_active', 'consultations', ['status'], 
                    postgresql_where=sa.text("status = 'active'"))
    op.create_index('idx_florist_profiles_active', 'florist_profiles', ['is_active'], 
                    postgresql_where=sa.text("is_active = true"))
    op.create_index('idx_products_category_active', 'products', ['category_id', 'is_active'])
    op.create_index('idx_orders_user_status', 'orders', ['user_id', 'status'])
    
    # 4. Добавляем constraints для безопасности
    op.create_check_constraint('chk_florist_rating', 'florist_profiles', 
                              sa.text('rating >= 0 AND rating <= 5'))
    op.create_check_constraint('chk_product_price', 'products', 
                              sa.text('price > 0'))
    op.create_check_constraint('chk_product_stock', 'products', 
                              sa.text('stock_qty >= 0'))
    op.create_check_constraint('chk_florist_review_rating', 'florist_reviews', 
                              sa.text('rating >= 1 AND rating <= 5'))


def downgrade() -> None:
    """Откат изменений."""
    
    # Удаляем constraints
    op.drop_constraint('chk_florist_review_rating', 'florist_reviews')
    op.drop_constraint('chk_product_stock', 'products')
    op.drop_constraint('chk_product_price', 'products')
    op.drop_constraint('chk_florist_rating', 'florist_profiles')
    
    # Удаляем индексы
    op.drop_index('idx_orders_user_status', 'orders')
    op.drop_index('idx_products_category_active', 'products')
    op.drop_index('idx_florist_profiles_active', 'florist_profiles')
    op.drop_index('idx_consultations_active', 'consultations')
    op.drop_index('idx_role_requests_status', 'role_requests')
    
    # Удаляем внешний ключ и столбец
    op.drop_constraint('fk_orders_florist', 'orders', type_='foreignkey')
    op.drop_column('orders', 'florist_id')
    
    # Удаляем добавленные поля
    op.drop_column('role_requests', 'lang')
    op.drop_column('role_requests', 'phone')
    op.drop_column('role_requests', 'last_name')
    op.drop_column('role_requests', 'first_name')