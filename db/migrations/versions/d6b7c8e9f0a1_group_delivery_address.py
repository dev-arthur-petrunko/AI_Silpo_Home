"""per-group delivery address (city/municipality) for city-specific scans

Revision ID: d6b7c8e9f0a1
Revises: c1e4f2a3b5d6
Create Date: 2026-08-06 15:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd6b7c8e9f0a1'
down_revision: Union[str, Sequence[str], None] = 'd2a5e3f4b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('groups') as batch_op:
        batch_op.add_column(sa.Column('delivery_address', sa.String(255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('groups') as batch_op:
        batch_op.drop_column('delivery_address')
