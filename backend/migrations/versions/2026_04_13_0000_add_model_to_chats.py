"""Add model column to chats

Revision ID: a1234567890
Revises: bd06a59c6be
Create Date: 2026-04-13 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1234567890'
down_revision: Union[str, None] = 'bd06a59c6be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('chats',
        sa.Column('model', sa.String(), nullable=False, server_default='pro')
    )

def downgrade() -> None:
    op.drop_column('chats', 'model')
