"""Fast org schema provisioning via template clone.

Clone the template schema by creating a new schema and copying all table
structures from the template schema.
"""
from sqlalchemy import text
from app.core.database import engine, AsyncSessionLocal
import logging
import re
import asyncio

logger = logging.getLogger(__name__)

TEMPLATE_SCHEMA = "template"
SLUG_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]*$')


async def provision_org_schema(org_slug: str) -> None:
    """
    Provision a new org schema by cloning the template schema structure:
    1. CREATE SCHEMA org_{slug}
    2. Clone all tables from template schema (structure only, no data)
    3. Update organizations.status to 'active'
    """
    if not SLUG_PATTERN.match(org_slug) or len(org_slug) > 50:
        raise ValueError(f"Invalid org slug format: {org_slug}")
    schema_name = f"org_{org_slug}"

    try:
        async with engine.begin() as conn:
            # Create the new schema
            await conn.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            logger.info(f"Created schema {schema_name}")

            # Get all tables in template schema
            tables_result = await conn.execute(text("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = :template_schema
            """), {"template_schema": TEMPLATE_SCHEMA})
            tables = [row[0] for row in tables_result.fetchall()]

            # Clone all tables concurrently to minimize total round-trip time
            # Each table creation is an independent operation, so parallelizing
            # them reduces overall provisioning latency while keeping transaction safety
            create_tasks = [
                conn.execute(text(f'''
                    CREATE TABLE "{schema_name}"."{table}"
                    (LIKE "{TEMPLATE_SCHEMA}"."{table}" INCLUDING ALL)
                '''))
                for table in tables
            ]
            await asyncio.gather(*create_tasks)
            logger.info(f"Cloned {len(tables)} tables to {schema_name}")

        # Update status to active
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


async def deprovision_org_schema(org_slug: str) -> None:
    """Drop org schema when org is deleted."""
    schema_name = f"org_{org_slug}"
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
            logger.info(f"Dropped schema {schema_name}")
    except Exception as e:
        logger.error(f"Failed to drop schema {schema_name}: {e}")
        raise
