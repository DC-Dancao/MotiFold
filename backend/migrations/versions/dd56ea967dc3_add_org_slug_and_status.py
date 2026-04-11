"""Add org_slug to workspaces and status to organizations

Revision ID: dd56ea967dc3
Revises: c71cbe4e716d
Create Date: 2026-04-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'dd56ea967dc3'
down_revision: Union[str, None] = 'c71cbe4e716d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add status column to organizations
    op.add_column('organizations',
        sa.Column('status', sa.String(), nullable=False, server_default='active'))

    # Add org_slug to workspaces (references organizations.slug)
    op.add_column('workspaces',
        sa.Column('org_slug', sa.String(50),
            sa.ForeignKey('organizations.slug', ondelete='SET NULL'),
            nullable=True))
    op.create_index(op.f('ix_workspaces_org_slug'), 'workspaces', ['org_slug'])

def downgrade() -> None:
    op.drop_index(op.f('ix_workspaces_org_slug'))
    op.drop_column('workspaces', 'org_slug')
    op.drop_column('organizations', 'status')