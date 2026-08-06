"""user contact fields (phone, address, contact_pending)

Revision ID: b5d3a8c1e2f4
Revises: a4c8e1f9b2d7
Create Date: 2026-08-06 13:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b5d3a8c1e2f4'
down_revision: Union[str, Sequence[str], None] = 'a4c8e1f9b2d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('phone_number', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('address', sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column('contact_pending', sa.Boolean(), nullable=False, server_default='false')
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('contact_pending')
        batch_op.drop_column('address')
        batch_op.drop_column('phone_number')
