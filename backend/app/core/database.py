from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from starlette.requests import Request

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()


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
