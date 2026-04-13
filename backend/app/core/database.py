from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from starlette.requests import Request

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI_PATH = BACKEND_DIR / "alembic.ini"

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()


def get_alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def _get_head_revision() -> str:
    return ScriptDirectory.from_config(get_alembic_config()).get_current_head()


def _get_current_revision(sync_conn) -> str | None:
    return MigrationContext.configure(sync_conn).get_current_revision()


async def repair_chat_model_columns() -> None:
    async with engine.begin() as conn:
        schemas_result = await conn.execute(text("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name = 'public'
               OR schema_name = 'template'
               OR schema_name LIKE 'org\\_%' ESCAPE '\\'
        """))
        schemas = [row[0] for row in schemas_result.fetchall()]

        preparer = conn.dialect.identifier_preparer

        for schema in schemas:
            has_chats = await conn.execute(text("""
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema
                  AND table_name = 'chats'
            """), {"schema": schema})
            if not has_chats.first():
                continue

            has_model = await conn.execute(text("""
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = 'chats'
                  AND column_name = 'model'
            """), {"schema": schema})
            if has_model.first():
                continue

            quoted_schema = preparer.quote(schema)
            await conn.execute(text(f'''
                ALTER TABLE {quoted_schema}."chats"
                ADD COLUMN model VARCHAR NOT NULL DEFAULT 'pro'
            '''))


async def ensure_schema_ready() -> None:
    expected_revision = _get_head_revision()

    async with engine.connect() as conn:
        current_revision = await conn.run_sync(_get_current_revision)

    if current_revision != expected_revision:
        raise RuntimeError("数据库 schema 未迁移到最新版本，请先执行 alembic upgrade head。")

    await repair_chat_model_columns()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def get_db_with_schema(request: Request):
    """Get DB session with search_path set to org schema if applicable."""
    org_schema = getattr(request.state, 'org_schema', None)
    async with AsyncSessionLocal() as session:
        if org_schema:
            from sqlalchemy import text
            await session.execute(text(f'SET LOCAL search_path TO "{org_schema}", public'))
        yield session
