"""початкова схема

Revision ID: 0cfc0ab385c1
Revises: 
Create Date: 2026-08-05 23:45:58.439482

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ідентифікатори ревізії, використовуються Alembic.
revision: str = '0cfc0ab385c1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Оновлення схеми."""
    # ### команди автоматично згенеровані Alembic — відкоригуйте за потреби! ###
    op.create_table('groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('telegram_chat_id', sa.BigInteger(), nullable=False),
    sa.Column('house_name', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_groups_telegram_chat_id'), 'groups', ['telegram_chat_id'], unique=True)
    op.create_table('deals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('mcp_product_id', sa.String(length=64), nullable=False),
    sa.Column('product_name', sa.String(length=512), nullable=False),
    sa.Column('image_url', sa.String(length=1024), nullable=True),
    sa.Column('unit_price_retail', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('unit_price_wholesale', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('wholesale_pack_size', sa.Integer(), nullable=False),
    sa.Column('savings_per_unit', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('status', sa.Enum('collecting', 'goal_reached', 'expired', 'cancelled', 'sent_to_manager', 'confirmed', name='deal_status'), server_default='collecting', nullable=False),
    sa.Column('telegram_message_id', sa.BigInteger(), nullable=True),
    sa.Column('deadline_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_deals_group_id'), 'deals', ['group_id'], unique=False)
    op.create_index(op.f('ix_deals_mcp_product_id'), 'deals', ['mcp_product_id'], unique=False)
    op.create_index(op.f('ix_deals_status'), 'deals', ['status'], unique=False)
    op.create_table('participants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('deal_id', sa.Integer(), nullable=False),
    sa.Column('telegram_user_id', sa.BigInteger(), nullable=False),
    sa.Column('telegram_username', sa.String(length=255), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('phone_number', sa.String(length=32), nullable=True),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('confirmed', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('deal_id', 'telegram_user_id', name='uq_participant_deal_user')
    )
    op.create_index(op.f('ix_participants_deal_id'), 'participants', ['deal_id'], unique=False)
    # ### кінець команд Alembic ###


def downgrade() -> None:
    """Відкат схеми."""
    # ### команди автоматично згенеровані Alembic — відкоригуйте за потреби! ###
    op.drop_index(op.f('ix_participants_deal_id'), table_name='participants')
    op.drop_table('participants')
    op.drop_index(op.f('ix_deals_status'), table_name='deals')
    op.drop_index(op.f('ix_deals_mcp_product_id'), table_name='deals')
    op.drop_index(op.f('ix_deals_group_id'), table_name='deals')
    op.drop_table('deals')
    op.drop_index(op.f('ix_groups_telegram_chat_id'), table_name='groups')
    op.drop_table('groups')
    # ### кінець команд Alembic ###
