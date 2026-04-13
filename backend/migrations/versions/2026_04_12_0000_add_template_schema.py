"""Add template schema for org schema cloning.

This migration creates a 'template' schema with all org-scoped tables.
New organization schemas are cloned from this template via:
    CREATE SCHEMA org_{slug} WITH TEMPLATE template

Revision ID: template_schema
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'template_schema'
down_revision = '1b2c3d4e5f6'  # Merge into main migration chain after organization_members
branch_labels = None
depends_on = None


def upgrade():
    # Create template schema
    op.execute("CREATE SCHEMA IF NOT EXISTS template")

    # Create all org-scoped tables in template schema
    # These MUST match the structure of tables in org schemas

    # keywords - from initial migration (6b6c7f6e8241)
    op.execute("""
        CREATE TABLE template.keywords (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            word VARCHAR NOT NULL,
            source_prompt VARCHAR,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_keywords_id ON template.keywords (id)")

    # workspaces - from initial migration (6b6c7f6e8241)
    # Plus org_slug column from dd56ea967dc3
    op.execute("""
        CREATE TABLE template.workspaces (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            name VARCHAR NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            org_slug VARCHAR(50)
        )
    """)
    op.execute("CREATE INDEX ix_workspaces_id ON template.workspaces (id)")
    op.execute("CREATE INDEX ix_workspaces_org_slug ON template.workspaces (org_slug)")

    # blackboards - from initial migration
    op.execute("""
        CREATE TABLE template.blackboards (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            workspace_id INTEGER,
            topic VARCHAR NOT NULL,
            content_json TEXT NOT NULL,
            status VARCHAR NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_blackboards_id ON template.blackboards (id)")

    # chats - from initial migration (note: column is 'title', not 'name')
    # Plus model column from a1234567890
    op.execute("""
        CREATE TABLE template.chats (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            workspace_id INTEGER,
            title VARCHAR,
            model VARCHAR NOT NULL DEFAULT 'pro',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_chats_id ON template.chats (id)")

    # morphological_analyses (matrices) - from initial migration
    op.execute("""
        CREATE TABLE template.morphological_analyses (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            workspace_id INTEGER,
            focus_question VARCHAR NOT NULL,
            parameters_json TEXT NOT NULL,
            matrix_json TEXT NOT NULL,
            status VARCHAR NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_morphological_analyses_id ON template.morphological_analyses (id)")

    # matrix_cells - child table of morphological_analyses
    op.execute("""
        CREATE TABLE template.matrix_cells (
            id SERIAL PRIMARY KEY,
            analysis_id INTEGER NOT NULL,
            pair_key VARCHAR(20) NOT NULL,
            state_pair VARCHAR(20) NOT NULL,
            status VARCHAR(10) NOT NULL,
            contradiction_type VARCHAR(1),
            reason TEXT
        )
    """)
    op.execute("CREATE INDEX ix_matrix_cells_id ON template.matrix_cells (id)")

    # solution_clusters - child table of morphological_analyses
    op.execute("""
        CREATE TABLE template.solution_clusters (
            id SERIAL PRIMARY KEY,
            analysis_id INTEGER NOT NULL,
            cluster_id VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            solution_indices JSON NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_solution_clusters_id ON template.solution_clusters (id)")

    # ahp_weights - child table of morphological_analyses
    op.execute("""
        CREATE TABLE template.ahp_weights (
            id SERIAL PRIMARY KEY,
            analysis_id INTEGER NOT NULL,
            criteria JSON NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_ahp_weights_id ON template.ahp_weights (id)")

    # messages - from initial migration
    op.execute("""
        CREATE TABLE template.messages (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER,
            role VARCHAR NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            idempotency_key VARCHAR
        )
    """)
    op.execute("CREATE INDEX ix_messages_id ON template.messages (id)")

    # research_reports - from 7c8d9e0f1234
    # Plus status and task_id columns from bd06a59c6be
    op.execute("""
        CREATE TABLE template.research_reports (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            workspace_id INTEGER,
            query TEXT NOT NULL,
            research_topic TEXT,
            report TEXT,
            notes_json TEXT NOT NULL,
            queries_json TEXT NOT NULL,
            level VARCHAR NOT NULL,
            iterations INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            status VARCHAR NOT NULL DEFAULT 'running',
            task_id VARCHAR
        )
    """)
    op.execute("CREATE INDEX ix_research_reports_id ON template.research_reports (id)")

    # memory_banks - from c1a2b3d4e5f6
    op.execute("""
        CREATE TABLE template.memory_banks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            config JSON DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # memory_units - from c1a2b3d4e5f6
    op.execute("""
        CREATE TABLE template.memory_units (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bank_id UUID NOT NULL,
            content TEXT NOT NULL,
            embedding TEXT,
            memory_type VARCHAR(50) DEFAULT 'fact',
            metadata JSON DEFAULT '{}',
            entity_ids UUID[] DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            mentioned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # entities - from c1a2b3d4e5f6
    op.execute("""
        CREATE TABLE template.entities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bank_id UUID NOT NULL,
            name TEXT NOT NULL,
            entity_type VARCHAR(50),
            canonical_name TEXT,
            metadata JSON DEFAULT '{}',
            mention_count INTEGER DEFAULT 1,
            first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # entity_memories - from c1a2b3d4e5f6
    op.execute("""
        CREATE TABLE template.entity_memories (
            entity_id UUID NOT NULL,
            memory_id UUID NOT NULL,
            PRIMARY KEY (entity_id, memory_id)
        )
    """)

    # Create indexes for memory tables
    op.execute("CREATE INDEX idx_memory_banks_workspace_id ON template.memory_banks (workspace_id)")
    op.execute("CREATE INDEX idx_memory_units_bank_id ON template.memory_units (bank_id)")
    op.execute("CREATE INDEX idx_memory_units_created_at ON template.memory_units (bank_id, created_at)")
    op.execute("CREATE INDEX idx_memory_units_memory_type ON template.memory_units (bank_id, memory_type)")
    op.execute("CREATE INDEX idx_entities_bank_id ON template.entities (bank_id)")
    op.execute("CREATE INDEX idx_entities_bank_name ON template.entities (bank_id, name)")

    # Create unique index on messages idempotency_key
    op.execute("CREATE UNIQUE INDEX ix_messages_idempotency_key ON template.messages (idempotency_key)")

    # Create index on research_reports task_id
    op.execute("CREATE INDEX ix_research_reports_task_id ON template.research_reports (task_id)")

    # Create foreign keys
    # Note: These reference public schema tables (users, organizations) and template schema tables
    # When org schemas are cloned, the FKs to public schema remain valid

    op.execute("""
        ALTER TABLE template.blackboards
        ADD CONSTRAINT fk_blackboards_user
        FOREIGN KEY (user_id) REFERENCES public.users(id)
    """)

    op.execute("""
        ALTER TABLE template.blackboards
        ADD CONSTRAINT fk_blackboards_workspace
        FOREIGN KEY (workspace_id) REFERENCES template.workspaces(id)
    """)

    op.execute("""
        ALTER TABLE template.chats
        ADD CONSTRAINT fk_chats_user
        FOREIGN KEY (user_id) REFERENCES public.users(id)
    """)

    op.execute("""
        ALTER TABLE template.chats
        ADD CONSTRAINT fk_chats_workspace
        FOREIGN KEY (workspace_id) REFERENCES template.workspaces(id)
    """)

    op.execute("""
        ALTER TABLE template.morphological_analyses
        ADD CONSTRAINT fk_morphological_analyses_user
        FOREIGN KEY (user_id) REFERENCES public.users(id)
    """)

    op.execute("""
        ALTER TABLE template.morphological_analyses
        ADD CONSTRAINT fk_morphological_analyses_workspace
        FOREIGN KEY (workspace_id) REFERENCES template.workspaces(id)
    """)

    op.execute("""
        ALTER TABLE template.matrix_cells
        ADD CONSTRAINT fk_matrix_cells_analysis
        FOREIGN KEY (analysis_id) REFERENCES template.morphological_analyses(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE template.solution_clusters
        ADD CONSTRAINT fk_solution_clusters_analysis
        FOREIGN KEY (analysis_id) REFERENCES template.morphological_analyses(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE template.ahp_weights
        ADD CONSTRAINT fk_ahp_weights_analysis
        FOREIGN KEY (analysis_id) REFERENCES template.morphological_analyses(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE template.messages
        ADD CONSTRAINT fk_messages_chat
        FOREIGN KEY (chat_id) REFERENCES template.chats(id)
    """)

    op.execute("""
        ALTER TABLE template.research_reports
        ADD CONSTRAINT fk_research_reports_user
        FOREIGN KEY (user_id) REFERENCES public.users(id)
    """)

    op.execute("""
        ALTER TABLE template.research_reports
        ADD CONSTRAINT fk_research_reports_workspace
        FOREIGN KEY (workspace_id) REFERENCES template.workspaces(id)
    """)

    op.execute("""
        ALTER TABLE template.memory_units
        ADD CONSTRAINT fk_memory_units_bank
        FOREIGN KEY (bank_id) REFERENCES template.memory_banks(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE template.memory_banks
        ADD CONSTRAINT fk_memory_banks_workspace
        FOREIGN KEY (workspace_id) REFERENCES template.workspaces(id)
    """)

    op.execute("""
        ALTER TABLE template.entities
        ADD CONSTRAINT fk_entities_bank
        FOREIGN KEY (bank_id) REFERENCES template.memory_banks(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE template.entity_memories
        ADD CONSTRAINT fk_entity_memories_entity
        FOREIGN KEY (entity_id) REFERENCES template.entities(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE template.entity_memories
        ADD CONSTRAINT fk_entity_memories_memory
        FOREIGN KEY (memory_id) REFERENCES template.memory_units(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE template.keywords
        ADD CONSTRAINT fk_keywords_user
        FOREIGN KEY (user_id) REFERENCES public.users(id)
    """)

    op.execute("""
        ALTER TABLE template.workspaces
        ADD CONSTRAINT fk_workspaces_user
        FOREIGN KEY (user_id) REFERENCES public.users(id)
    """)


def downgrade():
    op.execute("DROP SCHEMA IF EXISTS template CASCADE")
