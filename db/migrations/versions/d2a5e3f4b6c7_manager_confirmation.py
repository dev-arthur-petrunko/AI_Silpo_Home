"""поля статусу замовлення менеджера (manager_message_id, order_status)

Revision ID: d2a5e3f4b6c7
Revises: c1e4f2a3b5d6
Create Date: 2026-08-06 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# ідентифікатори ревізії, використовуються Alembic.
revision: str = 'd2a5e3f4b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1e4f2a3b5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Оновлення схеми."""
    with op.batch_alter_table('groups') as batch_op:
        batch_op.add_column(sa.Column('manager_message_id', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('order_status', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Відкат схеми."""
    with op.batch_alter_table('groups') as batch_op:
        batch_op.drop_column('order_status')
        batch_op.drop_column('manager_message_id')
