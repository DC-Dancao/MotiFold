"""Create tenant_migrations tracking table

Revision ID: 2026_04_14_0003
Revises: 2026_04_14_0002
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '2026_04_14_0003'
down_revision = '2026_04_14_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_migrations',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('migration_key', sa.String(length=255), nullable=False),
        sa.Column('task_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        schema='public',
    )
    op.create_unique_constraint(
        'uq_tenant_migrations_migration_key',
        'tenant_migrations',
        ['migration_key'],
        schema='public',
    )


def downgrade() -> None:
    op.drop_table('tenant_migrations', schema='public')
