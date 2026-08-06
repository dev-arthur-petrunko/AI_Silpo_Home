"""personalization and messages

Revision ID: a4c8e1f9b2d7
Revises: 3e9f7c2a1b8d
Create Date: 2026-08-06 12:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a4c8e1f9b2d7'
down_revision: Union[str, Sequence[str], None] = '3e9f7c2a1b8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'group_id',
            sa.Integer(),
            sa.ForeignKey('groups.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('telegram_user_id', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
    )
    op.create_index('ix_messages_group_id', 'messages', ['group_id'])
    op.create_index('ix_messages_created_at', 'messages', ['created_at'])

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('telegram_user_id', sa.BigInteger(), nullable=False),
        sa.Column('telegram_username', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_reminder_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.UniqueConstraint('telegram_user_id', name='uq_user_telegram_id'),
    )

    with op.batch_alter_table('groups') as batch_op:
        batch_op.add_column(sa.Column('profile_vector', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('tone_profile', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('groups') as batch_op:
        batch_op.drop_column('tone_profile')
        batch_op.drop_column('profile_vector')

    op.drop_table('users')
    op.drop_index('ix_messages_created_at', table_name='messages')
    op.drop_index('ix_messages_group_id', table_name='messages')
    op.drop_table('messages')
