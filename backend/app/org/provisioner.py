"""Async org schema provisioning using Alembic API."""
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from app.core.database import engine, AsyncSessionLocal, get_alembic_config
import logging

logger = logging.getLogger(__name__)

# Revision ID of the org schema tables migration
ORG_SCHEMA_TABLES_REVISION = '1b2c3d4e5f6'

async def provision_org_schema(org_slug: str) -> None:
    """
    Provision a new org schema:
    1. CREATE SCHEMA org_{slug}
    2. Run Alembic migration against new schema (creates all business tables)
    3. Update organizations.status to 'active'
    """
    schema_name = f"org_{org_slug}"

    try:
        # Step 1: Create schema
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
            logger.info(f"Created schema {schema_name}")

        # Step 2: Run Alembic migration against new schema using run_sync
        alembic_cfg = get_alembic_config()

        async def run_migrations_sync(connection):
            # Set search_path for this connection to the new schema
            connection.execute(text(f'SET search_path TO "{schema_name}", public'))

            # Run migration programmatically
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            migration_context = MigrationContext.configure(connection=connection)

            # Get and run the org schema tables migration
            revision = script_dir.get_revision(ORG_SCHEMA_TABLES_REVISION)
            if revision:
                migration_context.run_migration([revision])
                logger.info(f"Ran migration {ORG_SCHEMA_TABLES_REVISION} on schema {schema_name}")

        # Use async connection with run_sync for Alembic
        async with engine.connect() as conn:
            await conn.run_sync(run_migrations_sync)

        # Step 3: Update status to active
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE public.organizations SET status = 'active' WHERE slug = :slug"),
                {"slug": org_slug}
            )
            await session.commit()
            logger.info(f"Org {org_slug} is now active")

    except Exception as e:
        logger.error(f"Failed to provision schema for org {org_slug}: {e}")
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("UPDATE public.organizations SET status = 'failed' WHERE slug = :slug"),
                    {"slug": org_slug}
                )
                await session.commit()
        except Exception:
            pass
        raise
