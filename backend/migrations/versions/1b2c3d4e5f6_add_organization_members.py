"""Add organization_members table

Revision ID: 1b2c3d4e5f6
Revises: add_pg_trgm_extension
Create Date: 2026-04-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '1b2c3d4e5f6'
down_revision: Union[str, None] = 'add_pg_trgm_extension'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('organization_members',
    sa.Column('id', sa.String(100), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(20), nullable=False, server_default='member'),
    sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_member'),
    sa.ForeignKeyConstraint(['organization_id'], ['public.organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['public.users.id'], ondelete='CASCADE'),
    schema='public'
    )
    op.create_index(op.f('ix_organization_members_id'), 'organization_members', ['id'], unique=False, schema='public')
    op.create_index(op.f('ix_organization_members_organization_id'), 'organization_members', ['organization_id'], unique=False, schema='public')
    op.create_index(op.f('ix_organization_members_user_id'), 'organization_members', ['user_id'], unique=False, schema='public')


def downgrade() -> None:
    op.drop_index(op.f('ix_organization_members_user_id'), table_name='organization_members', schema='public')
    op.drop_index(op.f('ix_organization_members_organization_id'), table_name='organization_members', schema='public')
    op.drop_index(op.f('ix_organization_members_id'), table_name='organization_members', schema='public')
    op.drop_table('organization_members', schema='public')
