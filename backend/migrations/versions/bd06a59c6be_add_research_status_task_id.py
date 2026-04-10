"""Add status and task_id to research_reports

Revision ID: bd06a59c6be
Revises: 7c8d9e0f1234
Create Date: 2026-04-10 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'bd06a59c6be'
down_revision: Union[str, None] = '7c8d9e0f1234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('research_reports',
        sa.Column('status', sa.String(), nullable=False, server_default='running')
    )
    op.add_column('research_reports',
        sa.Column('task_id', sa.String(), nullable=True)
    )
    op.create_index('ix_research_reports_task_id', 'research_reports', ['task_id'], unique=False)

def downgrade() -> None:
    op.drop_index('ix_research_reports_task_id', table_name='research_reports')
    op.drop_column('research_reports', 'task_id')
    op.drop_column('research_reports', 'status')
