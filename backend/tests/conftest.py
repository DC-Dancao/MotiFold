import asyncio
import asyncpg
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from alembic import command
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings

# Parse the URL to get connection details for asyncpg
parsed_url = urlparse("postgresql+asyncpg://user:password@localhost:5434/motifold_test")
DB_USER = parsed_url.username
DB_PASSWORD = parsed_url.password
DB_HOST = parsed_url.hostname
DB_PORT = parsed_url.port
DB_NAME = parsed_url.path.lstrip("/")

async def ensure_test_database():
    try:
        conn = await asyncpg.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database="postgres"
        )
        # Check if test database exists
        exists = await conn.fetchval(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
        if not exists:
            await conn.execute(f"CREATE DATABASE {DB_NAME}")
        await conn.close()
    except Exception as e:
        print(f"Failed to ensure test database: {e}")

TEST_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5434/motifold_test"
settings.DATABASE_URL = TEST_DATABASE_URL

from app.core.security import get_current_user
from app.core.database import get_alembic_config, get_db
from app.main import app
from app.auth.models import User

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def reset_database():
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        await conn.exec_driver_sql("CREATE SCHEMA public")

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    await ensure_test_database()
    await reset_database()
    await asyncio.to_thread(command.upgrade, get_alembic_config(), "head")

    yield

    await reset_database()

@pytest_asyncio.fixture
async def db_session():
    """
    为每个测试提供一个干净的数据库会话。
    使用嵌套事务（SAVEPOINT），测试结束后回滚，速度极快。
    """
    async with engine.connect() as conn:
        # 开始一个外层事务
        await conn.begin()
        # 创建绑定到此连接的会话
        async with TestingSessionLocal(bind=conn) as session:
            # 开始嵌套事务
            await session.begin_nested()
            
            # 当程序调用 session.commit() 结束一个嵌套事务时，自动开启下一个嵌套事务
            @event.listens_for(session.sync_session, "after_transaction_end")
            def restart_savepoint(sync_session, transaction):
                if transaction.nested and not transaction._parent.nested:
                    sync_session.begin_nested()

            yield session
            
        # 测试结束后，外层事务自动回滚，撤销所有变更
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
    直接在数据库中创建一个测试用户，不走完整的 HTTP 注册流程。
    """
    user = User(username="testuser", password_hash="fakehash")
    db_session.add(user)
    await db_session.flush()
    # 强制让 ID 生效但不必真正 commit
    return user

@pytest_asyncio.fixture
async def auth_client(async_client, test_user):
    """
    自动注入当前测试用户的客户端。
    通过重写 get_current_user 绕过 JWT 校验。
    """
    async def override_get_current_user():
        return test_user
        
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield async_client
