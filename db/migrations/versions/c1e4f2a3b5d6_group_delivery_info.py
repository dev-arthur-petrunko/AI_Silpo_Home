"""group delivery info (city, address, delivery_time, phone) + checkout flag

Revision ID: c1e4f2a3b5d6
Revises: b5d3a8c1e2f4
Create Date: 2026-08-06 13:50:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c1e4f2a3b5d6'
down_revision: Union[str, Sequence[str], None] = 'b5d3a8c1e2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('groups') as batch_op:
        batch_op.add_column(sa.Column('delivery_info', sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column('checkout_pending', sa.Boolean(), nullable=False, server_default='false')
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('groups') as batch_op:
        batch_op.drop_column('checkout_pending')
        batch_op.drop_column('delivery_info')
