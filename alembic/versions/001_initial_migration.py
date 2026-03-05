"""initial migration

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('paid_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='unpaid'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('amount > 0', name='check_amount_positive'),
        sa.CheckConstraint('paid_amount >= 0', name='check_paid_amount_non_negative'),
        sa.CheckConstraint('paid_amount <= amount', name='check_paid_amount_not_exceed_total'),
        sa.CheckConstraint("status IN ('unpaid', 'partially_paid', 'paid')", name='check_order_status_valid')
    )

    op.create_index(op.f('ix_orders_id'), 'orders', ['id'], unique=False)
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)

    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('bank_payment_id', sa.String(100), nullable=True),
        sa.Column('bank_status', sa.String(50), nullable=True),
        sa.Column('bank_paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('amount > 0', name='check_payment_amount_positive'),
        sa.CheckConstraint("type IN ('cash', 'acquiring')", name='check_payment_type_valid'),
        sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'refunded')",
                           name='check_payment_status_valid')
    )

    op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=False)
    op.create_index(op.f('ix_payments_bank_payment_id'), 'payments', ['bank_payment_id'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)


def downgrade():
    op.drop_table('payments')
    op.drop_table('orders')