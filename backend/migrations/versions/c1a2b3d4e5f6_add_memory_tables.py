"""Add memory tables

Revision ID: c1a2b3d4e5f6
Revises: bd06a59c6be
Create Date: 2026-04-12 00:00:00.000000

This migration adds memory tables for workspace-level memory storage:
- memory_banks: One per workspace, provides data isolation
- memory_units: Individual memory entries with vector embeddings
- entities: Extracted entities from memories
- entity_memories: Entity-memory associations

Note: Requires pgvector extension to be installed on the database.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "bd06a59c6be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension (requires superuser or extension already available)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create memory_banks table
    op.create_table(
        "memory_banks",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("config", sa.JSON(), default={}),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("idx_memory_banks_workspace_id", "memory_banks", ["workspace_id"])

    # Create memory_units table
    # Note: Vector column is created as TEXT and cast to vector after table creation
    op.create_table(
        "memory_units",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bank_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),  # Temporary: cast to vector in separate step
        sa.Column("memory_type", sa.String(50), default="fact"),
        sa.Column("metadata", sa.JSON(), default={}),
        sa.Column("entity_ids", sa.ARRAY(sa.UUID()), default=[]),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("mentioned_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("idx_memory_units_bank_id", "memory_units", ["bank_id"])
    op.create_index("idx_memory_units_created_at", "memory_units", ["bank_id", "created_at"])
    op.create_index("idx_memory_units_memory_type", "memory_units", ["bank_id", "memory_type"])

    # Add foreign key for memory_units -> memory_banks
    op.create_foreign_key(
        "fk_memory_units_bank",
        "memory_units", "memory_banks",
        ["bank_id"], ["id"],
        ondelete="CASCADE",
    )

    # Create entities table
    op.create_table(
        "entities",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bank_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("canonical_name", sa.Text()),
        sa.Column("metadata", sa.JSON(), default={}),
        sa.Column("mention_count", sa.Integer(), default=1),
        sa.Column("first_seen", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("last_seen", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("idx_entities_bank_id", "entities", ["bank_id"])
    op.create_index("idx_entities_bank_name", "entities", ["bank_id", "name"])

    # Add foreign key for entities -> memory_banks
    op.create_foreign_key(
        "fk_entities_bank",
        "entities", "memory_banks",
        ["bank_id"], ["id"],
        ondelete="CASCADE",
    )

    # Create entity_memories association table
    op.create_table(
        "entity_memories",
        sa.Column("entity_id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("memory_id", sa.UUID(), nullable=False, primary_key=True),
    )

    # Add foreign keys for entity_memories
    op.create_foreign_key(
        "fk_entity_memories_entity",
        "entity_memories", "entities",
        ["entity_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_entity_memories_memory",
        "entity_memories", "memory_units",
        ["memory_id"], ["id"],
        ondelete="CASCADE",
    )

    # Convert embedding column to vector type
    # This requires pgvector extension
    op.execute("ALTER TABLE memory_units ALTER COLUMN embedding TYPE vector(1024)")


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table("entity_memories")
    op.drop_table("entities")
    op.drop_table("memory_units")
    op.drop_table("memory_banks")
