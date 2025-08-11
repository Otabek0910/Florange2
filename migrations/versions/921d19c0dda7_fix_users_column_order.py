"""fix_users_column_order

Revision ID: 921d19c0dda7
Revises: 3e17caacd615
Create Date: 2025-08-12 02:20:39.547960

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '921d19c0dda7'
down_revision: Union[str, Sequence[str], None] = '3e17caacd615'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Пересоздаем таблицу users с правильным порядком столбцов
    
    # 1. Создаем временную таблицу с правильным порядком
    op.execute("""
        CREATE TABLE users_new (
            id SERIAL PRIMARY KEY,
            tg_id VARCHAR(50) UNIQUE NOT NULL,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            phone VARCHAR(20),
            lang VARCHAR(5),
            role roleenum DEFAULT 'client',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # 2. Копируем данные из старой таблицы
    op.execute("""
        INSERT INTO users_new (id, tg_id, first_name, last_name, phone, lang, role, created_at)
        SELECT id, tg_id, first_name, last_name, phone, lang, role, created_at
        FROM users
    """)
    
    # 3. Обновляем sequence для id
    op.execute("SELECT setval('users_new_id_seq', (SELECT MAX(id) FROM users_new))")
    
    # 4. Удаляем старую таблицу и переименовываем новую
    op.execute("DROP TABLE users CASCADE")
    op.execute("ALTER TABLE users_new RENAME TO users")
    
    # 5. Восстанавливаем внешние ключи
    op.execute("ALTER TABLE orders ADD FOREIGN KEY (user_id) REFERENCES users(id)")
    op.execute("ALTER TABLE role_requests ADD FOREIGN KEY (user_id) REFERENCES users(id)")
    op.execute("ALTER TABLE role_requests ADD FOREIGN KEY (approved_by) REFERENCES users(id)")

def downgrade() -> None:
    # Откат не реализуем, так как это косметическое изменение
    pass