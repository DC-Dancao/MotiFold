"""Shared constants for tenant migrations.

This module defines migration keys and task names that must be kept in sync
between Alembic migrations and Celery worker tasks.

Note: Alembic migrations cannot import from this module (they run before app
initialization), so migrations use string literals that must match these constants.
"""
from typing import Final

# Migration 2026_04_14_0004: add_solutions_mode_to_tenant_chats
SOLUTIONS_MODE_MIGRATION_KEY: Final[str] = "2026_04_14_0004_add_solutions_mode_to_chats"
SOLUTIONS_MODE_TASK_NAME: Final[str] = "add_solutions_mode_to_chats"

# Migration 2026_04_14_0005: add_extra_data_to_memory_units
EXTRA_DATA_MIGRATION_KEY: Final[str] = "2026_04_14_0005_add_extra_data_to_memory_units"
EXTRA_DATA_TASK_NAME: Final[str] = "add_extra_data_to_memory_units"
