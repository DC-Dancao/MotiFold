from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
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


async def ensure_schema_ready() -> None:
    expected_revision = _get_head_revision()

    async with engine.connect() as conn:
        current_revision = await conn.run_sync(_get_current_revision)

    if current_revision != expected_revision:
        raise RuntimeError("数据库 schema 未迁移到最新版本，请先执行 alembic upgrade head。")

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
