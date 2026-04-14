"""Add solutions_mode to tenant chats

Revision ID: 2026_04_14_0002
Revises: 2026_04_14_0001
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '2026_04_14_0002'
down_revision = '2026_04_14_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get template and all tenant schemas that have a chats table
    conn = op.get_bind()
    result = conn.execute(text("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name = 'template'
           OR schema_name LIKE 'org\\_%' ESCAPE '\\'
    """))
    schemas = [row[0] for row in result.fetchall()]

    for schema in schemas:
        # Check if chats table exists in this schema
        table_exists = conn.execute(text("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = 'chats'
        """), {"schema": schema}).first()

        if not table_exists:
            continue

        # Check if solutions_mode column already exists
        col_exists = conn.execute(text("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = 'chats'
              AND column_name = 'solutions_mode'
        """), {"schema": schema}).first()

        if col_exists:
            continue

        # Add solutions_mode column to this schema's chats table
        op.execute(f'ALTER TABLE "{schema}"."chats" ADD COLUMN solutions_mode VARCHAR DEFAULT NULL')


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(text("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name = 'template'
           OR schema_name LIKE 'org\\_%' ESCAPE '\\'
    """))
    schemas = [row[0] for row in result.fetchall()]

    for schema in schemas:
        col_exists = conn.execute(text("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = 'chats'
              AND column_name = 'solutions_mode'
        """), {"schema": schema}).first()

        if col_exists:
            op.execute(f'ALTER TABLE "{schema}"."chats" DROP COLUMN solutions_mode')
