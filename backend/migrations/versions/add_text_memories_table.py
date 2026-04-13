"""add text_memories table

Revision ID: add_text_memories
Revises: abc123
Create Date: 2026-04-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'add_text_memories'
down_revision: Union[str, None] = 'abc123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'text_memories',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text("now()")),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index('idx_text_memories_workspace_id', 'text_memories', ['workspace_id'])


def downgrade() -> None:
    op.drop_index('idx_text_memories_workspace_id', table_name='text_memories')
    op.drop_table('text_memories')
