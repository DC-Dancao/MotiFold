# backend/tests/conftest.py
import asyncio
import os
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from alembic import command
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from app.core.security import get_current_user
from app.core.database import get_alembic_config, get_db
from app.main import app
from app.auth.models import User

# Parse the URL to get connection details for asyncpg
parsed_url = urlparse("postgresql+asyncpg://user:password@localhost:5434/motifold_test")
DB_USER = parsed_url.username
DB_PASSWORD = parsed_url.password
DB_HOST = parsed_url.hostname
DB_PORT = parsed_url.port
DB_NAME = parsed_url.path.lstrip("/")

async def ensure_test_database():
    try:
        import asyncpg
        conn = await asyncpg.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database="postgres"
        )
        exists = await conn.fetchval(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
        if not exists:
            await conn.execute(f"CREATE DATABASE {DB_NAME}")
        await conn.close()
    except Exception as e:
        print(f"Failed to ensure test database: {e}")

TEST_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5434/motifold_test"
settings.DATABASE_URL = TEST_DATABASE_URL

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def reset_database():
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        await conn.exec_driver_sql("CREATE SCHEMA public")

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    if os.environ.get("SKIP_DB_SETUP"):
        yield
        return
    try:
        await ensure_test_database()
        await reset_database()
        await asyncio.to_thread(command.upgrade, get_alembic_config(), "head")
    except Exception:
        yield
        return
    yield
    try:
        await reset_database()
    except Exception:
        pass

@pytest_asyncio.fixture
async def db_session():
    """
    为每个测试提供一个干净的数据库会话。
    使用嵌套事务（SAVEPOINT），测试结束后回滚，速度极快。
    """
    async with engine.connect() as conn:
        await conn.begin()
        async with TestingSessionLocal(bind=conn) as session:
            await session.begin_nested()

            @event.listens_for(session.sync_session, "after_transaction_end")
            def restart_savepoint(sync_session, transaction):
                if transaction.nested and not transaction._parent.nested:
                    sync_session.begin_nested()

            yield session

        await conn.rollback()

@pytest_asyncio.fixture
async def async_client(db_session):
    """
    提供异步 HTTP 客户端，并自动重写数据库依赖。
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def test_user(db_session):
    """
    直接在数据库中创建一个测试用户。
    """
    user = User(username="testuser", password_hash="fakehash")
    db_session.add(user)
    await db_session.flush()
    return user

@pytest_asyncio.fixture
async def other_user(db_session):
    """
    Create a second test user for tests requiring multiple users.
    """
    user = User(username="otheruser", password_hash="fakehash")
    db_session.add(user)
    await db_session.flush()
    return user

@pytest_asyncio.fixture
async def auth_client(async_client, test_user):
    """
    自动注入当前测试用户的客户端。
    """
    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield async_client
