"""Background tasks for tenant schema migrations.

Processes tenant schema updates asynchronously via Celery to avoid
long-running transactions during alembic upgrade.

Constants are imported from app.core.tenant_migration_constants to ensure
migrations and tasks stay in sync.
"""
import json
import logging

from celery import shared_task
from celery.schedules import crontab
from psycopg2 import sql
from sqlalchemy import text

from app.core.tenant_migration_constants import (
    SOLUTIONS_MODE_MIGRATION_KEY,
    SOLUTIONS_MODE_TASK_NAME,
    EXTRA_DATA_MIGRATION_KEY,
    EXTRA_DATA_TASK_NAME,
)
from app.worker import celery_app

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


def get_sync_db_connection():
    """Get a synchronous psycopg2 connection."""
    import psycopg2
    from app.core.config import settings
    # Convert asyncpg URL to psycopg2 URL
    db_url = settings.DATABASE_URL.replace('+asyncpg', '')
    return psycopg2.connect(db_url)


def check_and_add_column_to_chats(conn, schema: str, column: str) -> bool:
    """
    Check if column exists in chats table and add if missing, all within the same connection.
    Returns True if column was added, False if it already existed.
    Uses identifier quoting to prevent SQL injection.
    """
    try:
        with conn.cursor() as cur:
            # Check if column exists
            cur.execute("""
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'chats'
                  AND column_name = %s
            """, (schema, column))
            if cur.fetchone():
                return False

            # Column doesn't exist, add it with proper identifier quoting
            # Note: column and schema use Identifier, but VARCHAR is a type token (not quoted)
            query = sql.SQL('ALTER TABLE {}.{} ADD COLUMN IF NOT EXISTS {} VARCHAR').format(
                sql.Identifier(schema),
                sql.Identifier('chats'),
                sql.Identifier(column),
            )
            cur.execute(query)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def check_and_add_extra_data_to_memory_units(conn, schema: str) -> bool:
    """
    Check if extra_data column exists in memory_units table and add if missing.
    Returns True if column was added, False if it already existed.
    Uses identifier quoting to prevent SQL injection.
    """
    try:
        with conn.cursor() as cur:
            # Check if column exists
            cur.execute("""
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'memory_units'
                  AND column_name = 'extra_data'
            """, (schema,))
            if cur.fetchone():
                return False

            # Column doesn't exist, add it with proper identifier quoting
            # Note: Use format with escaped braces since JSON default '{}' would be interpreted as format placeholder
            query = sql.SQL('ALTER TABLE {}.{} ADD COLUMN IF NOT EXISTS {} JSON DEFAULT {{}}').format(
                sql.Identifier(schema),
                sql.Identifier('memory_units'),
                sql.Identifier('extra_data'),
            )
            cur.execute(query)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_add_solutions_mode_to_chats(self) -> dict:
    """
    Process tenant migration: add solutions_mode to all tenant chats tables.

    This task:
    1. Marks the migration as 'running'
    2. Finds all tenant schemas
    3. Adds solutions_mode column to each (idempotent via IF NOT EXISTS)
    4. Updates status to 'completed' or 'failed'
    """
    conn = get_sync_db_connection()
    try:
        # Get and lock the migration record
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, status
                FROM public.tenant_migrations
                WHERE migration_key = %s
                FOR UPDATE
            """, (SOLUTIONS_MODE_MIGRATION_KEY,))
            row = cur.fetchone()

        if not row:
            logger.error(f"Migration {SOLUTIONS_MODE_MIGRATION_KEY} not found in tenant_migrations")
            return {'status': 'missing'}

        _, current_status = row

        # Allow re-running if previous attempt ended with errors (beat only picks up 'pending')
        if current_status == 'completed':
            logger.info(f"Migration {SOLUTIONS_MODE_MIGRATION_KEY} already completed")
            return {'status': 'already_completed'}

        # Mark as running
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.tenant_migrations
                SET status = 'running',
                    started_at = COALESCE(started_at, NOW()),
                    updated_at = NOW(),
                    error_message = NULL
                WHERE migration_key = %s
            """, (SOLUTIONS_MODE_MIGRATION_KEY,))
        conn.commit()

        # Get all tenant schemas (exclude template and public)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name LIKE 'org\\_%%' ESCAPE '\\'
                ORDER BY schema_name
            """)
            schemas = [row[0] for row in cur.fetchall()]

        processed = 0
        failed = []

        for schema in schemas:
            try:
                added = check_and_add_column_to_chats(conn, schema, 'solutions_mode')
                if added:
                    logger.info(f"Migration {SOLUTIONS_MODE_MIGRATION_KEY}: added solutions_mode to {schema}")
                processed += 1

            except Exception as exc:
                failed.append({'schema': schema, 'error': str(exc)})
                logger.error(f"Migration {SOLUTIONS_MODE_MIGRATION_KEY}: failed for {schema}: {exc}")

        # Determine final status
        final_status = 'completed' if not failed else 'completed_with_errors'
        error_msg = f"{len(failed)} tenant schemas failed" if failed else None

        # Update migration record
        result_payload = json.dumps({
            'processed': processed,
            'failed_count': len(failed),
            'failed': failed,
        })

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.tenant_migrations
                SET status = %s,
                    completed_at = NOW(),
                    updated_at = NOW(),
                    error_message = %s,
                    payload = %s::jsonb
                WHERE migration_key = %s
            """, (final_status, error_msg, result_payload, SOLUTIONS_MODE_MIGRATION_KEY))
        conn.commit()

        logger.info(f"Migration {SOLUTIONS_MODE_MIGRATION_KEY}: {final_status}, processed={processed}, failed={len(failed)}")
        return {
            'status': final_status,
            'processed': processed,
            'failed_count': len(failed),
        }

    except Exception as exc:
        conn.rollback()
        logger.error(f"Migration {SOLUTIONS_MODE_MIGRATION_KEY} crashed: {exc}")

        # Mark as failed
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.tenant_migrations
                SET status = 'failed',
                    updated_at = NOW(),
                    error_message = %s
                WHERE migration_key = %s
            """, (f'Worker crashed: {exc}', SOLUTIONS_MODE_MIGRATION_KEY))
        conn.commit()

        raise self.retry(exc=exc)

    finally:
        conn.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_add_extra_data_to_memory_units(self) -> dict:
    """
    Process tenant migration: add extra_data to all tenant memory_units tables.

    This task:
    1. Marks the migration as 'running'
    2. Finds all tenant schemas
    3. Adds extra_data column to each (idempotent via IF NOT EXISTS)
    4. Updates status to 'completed' or 'failed'
    """
    conn = get_sync_db_connection()
    try:
        # Get and lock the migration record
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, status
                FROM public.tenant_migrations
                WHERE migration_key = %s
                FOR UPDATE
            """, (EXTRA_DATA_MIGRATION_KEY,))
            row = cur.fetchone()

        if not row:
            logger.error(f"Migration {EXTRA_DATA_MIGRATION_KEY} not found in tenant_migrations")
            return {'status': 'missing'}

        _, current_status = row

        # Allow re-running if previous attempt ended with errors (beat only picks up 'pending')
        if current_status == 'completed':
            logger.info(f"Migration {EXTRA_DATA_MIGRATION_KEY} already completed")
            return {'status': 'already_completed'}

        # Mark as running
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.tenant_migrations
                SET status = 'running',
                    started_at = COALESCE(started_at, NOW()),
                    updated_at = NOW(),
                    error_message = NULL
                WHERE migration_key = %s
            """, (EXTRA_DATA_MIGRATION_KEY,))
        conn.commit()

        # Get all tenant schemas (exclude template and public)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name LIKE 'org\\_%%' ESCAPE '\\'
                ORDER BY schema_name
            """)
            schemas = [row[0] for row in cur.fetchall()]

        processed = 0
        failed = []

        for schema in schemas:
            try:
                added = check_and_add_extra_data_to_memory_units(conn, schema)
                if added:
                    logger.info(f"Migration {EXTRA_DATA_MIGRATION_KEY}: added extra_data to {schema}")
                processed += 1

            except Exception as exc:
                failed.append({'schema': schema, 'error': str(exc)})
                logger.error(f"Migration {EXTRA_DATA_MIGRATION_KEY}: failed for {schema}: {exc}")

        # Determine final status
        final_status = 'completed' if not failed else 'completed_with_errors'
        error_msg = f"{len(failed)} tenant schemas failed" if failed else None

        # Update migration record
        result_payload = json.dumps({
            'processed': processed,
            'failed_count': len(failed),
            'failed': failed,
        })

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.tenant_migrations
                SET status = %s,
                    completed_at = NOW(),
                    updated_at = NOW(),
                    error_message = %s,
                    payload = %s::jsonb
                WHERE migration_key = %s
            """, (final_status, error_msg, result_payload, EXTRA_DATA_MIGRATION_KEY))
        conn.commit()

        logger.info(f"Migration {EXTRA_DATA_MIGRATION_KEY}: {final_status}, processed={processed}, failed={len(failed)}")
        return {
            'status': final_status,
            'processed': processed,
            'failed_count': len(failed),
        }

    except Exception as exc:
        conn.rollback()
        logger.error(f"Migration {EXTRA_DATA_MIGRATION_KEY} crashed: {exc}")

        # Mark as failed
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.tenant_migrations
                SET status = 'failed',
                    updated_at = NOW(),
                    error_message = %s
                WHERE migration_key = %s
            """, (f'Worker crashed: {exc}', EXTRA_DATA_MIGRATION_KEY))
        conn.commit()

        raise self.retry(exc=exc)

    finally:
        conn.close()


@celery_app.task
def enqueue_pending_migrations() -> dict:
    """
    Scan tenant_migrations for pending tasks and dispatch them once per task_name.

    This is called periodically by Celery beat to ensure any pending
    migrations that weren't triggered manually are eventually processed.

    Note: Beat only picks up migrations with status='pending'. For re-running
    failed migrations (status='completed_with_errors'), use the manual trigger
    script or call this task directly. This separation prevents beat from
    auto-retrying migrations that need human review after errors.

    Dispatches at most one task per unique task_name to avoid duplicate processing.
    """
    conn = get_sync_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT task_name
                FROM public.tenant_migrations
                WHERE status = 'pending'
                ORDER BY task_name
            """)
            pending_task_names = [row[0] for row in cur.fetchall()]

        if not pending_task_names:
            logger.debug("No pending tenant migrations found.")
            return {'dispatched': [], 'count': 0}

        dispatched = []
        for task_name in pending_task_names:
            if task_name == SOLUTIONS_MODE_TASK_NAME:
                run_add_solutions_mode_to_chats.delay()
                dispatched.append(task_name)
                logger.info(f"Dispatched task for pending migrations with task_name={task_name}")
            elif task_name == EXTRA_DATA_TASK_NAME:
                run_add_extra_data_to_memory_units.delay()
                dispatched.append(task_name)
                logger.info(f"Dispatched task for pending migrations with task_name={task_name}")

        return {'dispatched': dispatched, 'count': len(dispatched)}

    finally:
        conn.close()


# Celery beat schedule: safely merge with existing beat_schedule
# Don't override any existing beat tasks from other modules
_tenant_beat_task = {
    'task': 'app.worker.tenant_migration_tasks.enqueue_pending_migrations',
    'schedule': crontab(minute='*'),  # every minute
}
# Merge with existing beat_schedule instead of replacing
celery_app.conf.beat_schedule = {
    **(celery_app.conf.get('beat_schedule') or {}),
    'check-pending-tenant-migrations': _tenant_beat_task,
}
