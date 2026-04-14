#!/usr/bin/env python
"""Trigger pending tenant migrations after alembic upgrade.

Run this script after `alembic upgrade head` to dispatch any pending
tenant schema migrations to Celery workers.

Usage:
    python trigger_tenant_migrations.py

Or via Celery directly:
    celery -A app.worker call enqueue_pending_migrations
"""
import sys
import os

# Add the backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Main entry point."""
    print("Checking for pending tenant migrations...")

    # Import here to avoid issues if psycopg2 not available in all environments
    import psycopg2
    from app.core.config import settings

    # First check if tenant_migrations table exists
    db_url = settings.DATABASE_URL.replace('+asyncpg', '')
    conn = psycopg2.connect(db_url)

    try:
        # Check if table exists
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'tenant_migrations'
            """)
            table_exists = cur.fetchone() is not None

        if not table_exists:
            print("tenant_migrations table does not exist yet.")
            print("Run 'alembic upgrade head' first to create it.")
            return 1

        # Check for pending or failed migrations - only need distinct task names
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT task_name
                FROM public.tenant_migrations
                WHERE status IN ('pending', 'completed_with_errors')
                ORDER BY task_name
            """)
            task_names = [row[0] for row in cur.fetchall()]

        if not task_names:
            print("No pending or failed tenant migrations found.")
            return 0

        print(f"Found {len(task_names)} migration task type(s) to dispatch:")
        for task_name in task_names:
            print(f"  - {task_name}")

        # Dispatch once per task type via Celery
        from app.worker.tenant_migration_tasks import (
            run_add_solutions_mode_to_chats,
            run_add_extra_data_to_memory_units,
        )

        print("\nDispatching migration tasks...")
        dispatched = 0
        for task_name in task_names:
            if task_name == 'add_solutions_mode_to_chats':
                run_add_solutions_mode_to_chats.delay()
                dispatched += 1
            elif task_name == 'add_extra_data_to_memory_units':
                run_add_extra_data_to_memory_units.delay()
                dispatched += 1
            else:
                print(f"  Warning: unknown task_name '{task_name}'")

        print(f"\nDispatched {dispatched} migration task(s) to Celery.")
        print("Check Celery worker logs for progress.")
        print("\nNote: Celery beat also checks for pending migrations every minute.")
        return 0

    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
