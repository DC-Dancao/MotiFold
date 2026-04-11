"""Add pg_trgm extension for entity similarity

Revision ID: add_pg_trgm_extension
Revises: c1a2b3d4e5f6
Create Date: 2026-04-12 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, func

revision: str = "add_pg_trgm_extension"
down_revision: Union[str, None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pg_trgm extension for similarity search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Add trigram index on entity name for fast similarity search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_entities_name_trgm
        ON entities
        USING gin (name gin_trgm_ops)
    """)

    # Also add index for exact lookups (case-insensitive)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_entities_bank_name_lower
        ON entities (bank_id, lower(name))
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_entities_bank_name_lower")
    op.execute("DROP INDEX IF EXISTS idx_entities_name_trgm")
    # Don't drop extension as other things might use it