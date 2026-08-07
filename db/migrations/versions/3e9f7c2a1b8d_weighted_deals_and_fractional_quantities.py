"""вагові угоди та дробові кількості

Revision ID: 3e9f7c2a1b8d
Revises: 0cfc0ab385c1
Create Date: 2026-08-06 10:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# ідентифікатори ревізії, використовуються Alembic.
revision: str = '3e9f7c2a1b8d'
down_revision: Union[str, Sequence[str], None] = '0cfc0ab385c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Оновлення схеми."""
    # Вагові товари (за кг) мають дробовий мінімальний обсяг замовлення,
    # напр. wholesale_pack_size = 0.5 (кг) замість 3 (шт).
    with op.batch_alter_table('deals') as batch_op:
        batch_op.alter_column(
            'wholesale_pack_size',
            existing_type=sa.Integer(),
            type_=sa.Numeric(precision=10, scale=3),
            existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column('weighted', sa.Boolean(), server_default='false', nullable=False)
        )

    with op.batch_alter_table('participants') as batch_op:
        batch_op.alter_column(
            'quantity',
            existing_type=sa.Integer(),
            type_=sa.Numeric(precision=10, scale=3),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Відкат схеми."""
    with op.batch_alter_table('participants') as batch_op:
        batch_op.alter_column(
            'quantity',
            existing_type=sa.Numeric(precision=10, scale=3),
            type_=sa.Integer(),
            existing_nullable=False,
        )

    with op.batch_alter_table('deals') as batch_op:
        batch_op.drop_column('weighted')
        batch_op.alter_column(
            'wholesale_pack_size',
            existing_type=sa.Numeric(precision=10, scale=3),
            type_=sa.Integer(),
            existing_nullable=False,
        )
