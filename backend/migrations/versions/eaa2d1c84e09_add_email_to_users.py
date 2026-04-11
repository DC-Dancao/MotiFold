"""Add email to users

Revision ID: eaa2d1c84e09
Revises: dd56ea967dc3
Create Date: 2026-04-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'eaa2d1c84e09'
down_revision: Union[str, None] = 'dd56ea967dc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('users', sa.Column('email', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'email')
