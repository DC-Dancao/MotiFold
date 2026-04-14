"""Add extra_data to memory_units

Revision ID: 2026_04_14_0001
Revises: 2026_04_14_0000
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026_04_14_0001'
down_revision = '2026_04_14_0000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('memory_units', sa.Column('extra_data', sa.JSON(), nullable=True, server_default='{}'))


def downgrade() -> None:
    op.drop_column('memory_units', 'extra_data')