"""Add solutions_mode to chats

Revision ID: 2026_04_14_0000
Revises: add_text_memories
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026_04_14_0000'
down_revision = 'add_text_memories'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('chats', sa.Column('solutions_mode', sa.String(), nullable=True, server_default=None))


def downgrade() -> None:
    op.drop_column('chats', 'solutions_mode')
