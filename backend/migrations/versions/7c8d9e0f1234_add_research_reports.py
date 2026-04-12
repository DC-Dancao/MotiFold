"""Add research_reports table

Revision ID: 7c8d9e0f1234
Revises: 6b6c7f6e8241
Create Date: 2026-04-09 18:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c8d9e0f1234'
down_revision: Union[str, None] = 'eaa2d1c84e09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('research_reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('workspace_id', sa.Integer(), nullable=True),
    sa.Column('query', sa.Text(), nullable=False),
    sa.Column('research_topic', sa.Text(), nullable=True),
    sa.Column('report', sa.Text(), nullable=True),
    sa.Column('notes_json', sa.Text(), nullable=False),
    sa.Column('queries_json', sa.Text(), nullable=False),
    sa.Column('level', sa.String(), nullable=False),
    sa.Column('iterations', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_reports_id'), 'research_reports', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_research_reports_id'), table_name='research_reports')
    op.drop_table('research_reports')
