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
from app.core.database import get_alembic_config, get_db, get_db_with_schema
from app.main import app
from app.auth.models import User
from app.org.dependencies import get_current_org_membership
from app.org.models import OrganizationMember

# Pseudo-org slug used by the auth_client fixture below. Tests that need
# to assert against a specific tenant context should override the
# X-Org-ID header on the client themselves.
TEST_ORG_SLUG = "testorg"

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
async def auth_client(async_client, db_session, test_user):
    """
    自动注入当前测试用户的客户端。

    Also wires up the tenant boundary so the request actually flows
    through the new ``/api/*`` routes:

    * Ships an ``X-Org-ID`` header on every request, so the
      ``TenantMiddleware`` sets a non-None org context (mirroring what
      the frontend always sends after the routing refactor).
    * Stubs ``get_current_org_membership`` so endpoints don't 400 on a
      missing real organization row (which the SAVEPOINT-based test
      session can't safely create — provisioning lives outside the
      session and would pollute the database).
    * Stubs ``get_db_with_schema`` to reuse the per-test session
      without attempting ``SET LOCAL search_path`` to an unprovisioned
      org schema.

    Caveat — the membership stub means tests CANNOT use ``auth_client``
    to assert the membership 403 path (missing/insufficient role) or
    the org-not-active 503 path; the stub bypasses both. Tests that
    need those negative paths should use ``async_client`` and override
    ``get_current_user`` themselves, or call the endpoint without
    ``X-Org-ID``.

    Tests that *do* want to exercise the real provisioner/search_path
    path should opt out and use ``async_client`` + a session-scoped org
    fixture instead.
    """
    async def override_get_current_user():
        return test_user

    async def override_get_org_membership():
        # OrganizationMember.id is String(100) following the convention
        # ``"{org_id}_{user_id}"`` (see app/org/models.py). organization_id
        # is hard-coded to 1 because no current endpoint re-fetches the
        # org row via membership.organization_id — only membership.role
        # is consulted (in app/org/dependencies.py:require_org_role).
        # If a future endpoint starts re-querying via this attribute the
        # test will fail loudly with a missing-row error rather than
        # silently — that's intentional.
        return OrganizationMember(
            id=f"1_{test_user.id}",
            organization_id=1,
            user_id=test_user.id,
            role="owner",
        )

    async def override_get_db_with_schema():
        yield db_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_org_membership] = override_get_org_membership
    app.dependency_overrides[get_db_with_schema] = override_get_db_with_schema
    async_client.headers["X-Org-ID"] = TEST_ORG_SLUG

    try:
        yield async_client
    finally:
        async_client.headers.pop("X-Org-ID", None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_org_membership, None)
        app.dependency_overrides.pop(get_db_with_schema, None)
