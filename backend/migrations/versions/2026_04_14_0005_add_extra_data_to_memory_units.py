"""add extra_data to template memory_units and enqueue tenant migration

Revision ID: 2026_04_14_0005
Revises: 2026_04_14_0004
Create Date: 2026-04-15

This migration:
1. Applies extra_data to the template schema immediately (idempotent)
2. Enqueues a task to public.tenant_migrations for tenant fan-out

The actual tenant schema updates are processed asynchronously by
app.worker.tenant_migration_tasks to avoid long-running transactions
during alembic upgrade.

Downgrade note: Only reverts the template schema and removes any
not-yet-started tenant migration record. Tenant schemas already
migrated asynchronously are not rolled back by this Alembic downgrade.
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '2026_04_14_0005'
down_revision = '2026_04_14_0004'
branch_labels = None
depends_on = None

MIGRATION_KEY = '2026_04_14_0005_add_extra_data_to_memory_units'
TASK_NAME = 'add_extra_data_to_memory_units'


def upgrade() -> None:
    conn = op.get_bind()

    # 1) template schema: apply immediately and idempotently
    conn.execute(text("""
        ALTER TABLE IF EXISTS "template"."memory_units"
        ADD COLUMN IF NOT EXISTS extra_data JSON DEFAULT '{}'
    """))

    # 2) enqueue tenant migration once (idempotent via ON CONFLICT DO NOTHING)
    conn.execute(text("""
        INSERT INTO public.tenant_migrations (
            migration_key,
            task_name,
            status,
            payload,
            created_at,
            updated_at
        )
        VALUES (
            :migration_key,
            :task_name,
            'pending',
            '{}'::jsonb,
            NOW(),
            NOW()
        )
        ON CONFLICT (migration_key) DO NOTHING;
    """), {'migration_key': MIGRATION_KEY, 'task_name': TASK_NAME})


def downgrade() -> None:
    conn = op.get_bind()

    # rollback template schema only
    conn.execute(text("""
        ALTER TABLE IF EXISTS "template"."memory_units"
        DROP COLUMN IF EXISTS extra_data
    """))

    # remove pending record only (don't remove if already executed)
    conn.execute(text("""
        DELETE FROM public.tenant_migrations
        WHERE migration_key = :migration_key
          AND status = 'pending'
    """), {'migration_key': MIGRATION_KEY})
