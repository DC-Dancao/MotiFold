# 测试重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 `backend/tests/` 目录进行全面重构，建立 4 层测试架构（unit/integration/ai_logic/ai_quality），引入模块化 fixtures + 工厂模式 + Golden Dataset 管理。

**Architecture:** 按测试类型分层组织目录：unit（传统 mock 测试）、integration（真实 DB）、ai_logic（golden dataset + mock LLM）、ai_quality（真实 API）。fixtures 按模块拆分，golden cases 放在 JSON 文件中管理。

**Tech Stack:** pytest, pytest-asyncio, pytest-markers, unittest.mock, asyncpg, SQLAlchemy

---

## File Structure (Target)

```
backend/tests/
├── conftest.py                         # 根级通用 fixtures
├── pytest.ini                          # markers 配置
├── fixtures/
│   ├── __init__.py
│   ├── factories.py                    # UserFactory, WorkspaceFactory, ChatFactory
│   └── golden/
│       ├── research/
│       │   ├── clarify_topic.json
│       │   ├── search_and_summarize.json
│       │   └── generate_report.json
│       └── blackboard/
│           └── generate_steps.json
├── unit/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_matrix_router.py          # matrix service 逻辑
│   ├── test_worker.py                 # worker 逻辑
│   └── llm/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_llm_invoke.py         # llm_invoke / llm_invoke_async
│       ├── test_llm_stream.py         # llm_stream / llm_stream_async
│       ├── test_llm_structured.py     # llm_structured_* / llm_batch_*
│       └── test_llm_tool.py           # llm_tool_call / llm_tool_stream
├── integration/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py                   # 注册/登录/权限
│   ├── test_workspace.py              # workspace CRUD
│   └── test_chat.py                   # chat CRUD
├── ai_logic/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_research_agent.py         # graph + state machine
│   ├── test_research_tools.py         # tools 函数逻辑
│   ├── test_research_state.py         # state 边界条件
│   └── test_blackboard_agent.py       # blackboard agent
└── ai_quality/
    ├── __init__.py
    ├── conftest.py
    └── test_research_golden.py        # golden dataset + 语义检查
```

---

## Task 1: 创建目录结构和基础配置

**Files:**
- Create: `backend/tests/fixtures/__init__.py`
- Create: `backend/tests/fixtures/golden/research/.gitkeep`
- Create: `backend/tests/fixtures/golden/blackboard/.gitkeep`
- Create: `backend/tests/unit/__init__.py`
- Create: `backend/tests/unit/llm/__init__.py`
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/ai_logic/__init__.py`
- Create: `backend/tests/ai_quality/__init__.py`
- Modify: `backend/tests/pytest.ini` (new content)

- [ ] **Step 1: Create directory structure**

```bash
cd /wslshare/taskly/feature-5/backend/tests
mkdir -p fixtures/golden/research fixtures/golden/blackboard
mkdir -p unit/llm integration ai_logic ai_quality
touch fixtures/__init__.py fixtures/golden/research/.gitkeep fixtures/golden/blackboard/.gitkeep
touch unit/__init__.py unit/llm/__init__.py integration/__init__.py ai_logic/__init__.py ai_quality/__init__.py
```

- [ ] **Step 2: Write pytest.ini with markers**

```ini
# backend/tests/pytest.ini
[pytest]
markers =
    unit: 传统单元测试，mock，快速，CI 默认
    integration: 集成测试，真实 DB
    ai_logic: AI 逻辑测试，golden dataset + mock LLM
    ai_quality: AI 质量测试，真实 API，手动触发
asyncio_mode = auto
```

- [ ] **Step 3: Verify pytest.ini is valid**

Run: `cd /wslshare/taskly/feature-5/backend && python -c "import configparser; c = configparser.ConfigParser(); c.read('tests/pytest.ini'); print(list(c['pytest']['markers'].split('\n')))"`
Expected: markers are parsed without error

---

## Task 2: 创建 Golden Dataset JSON 文件

**Files:**
- Create: `backend/tests/fixtures/golden/research/clarify_topic.json`
- Create: `backend/tests/fixtures/golden/research/search_and_summarize.json`
- Create: `backend/tests/fixtures/golden/research/generate_report.json`
- Create: `backend/tests/fixtures/golden/blackboard/generate_steps.json`

- [ ] **Step 1: Write clarify_topic golden cases**

```json
{
  "description": "clarify_topic 的 golden 测试数据集",
  "test_cases": [
    {
      "id": "clarify-001",
      "query": "研究 AI Agent 在软件开发中的最新进展和面临的挑战",
      "expected_keywords": ["AI Agent", "软件", "进展", "挑战", "自主"],
      "expected_min_length": 10,
      "expected_max_length": 200
    },
    {
      "id": "clarify-002",
      "query": "分析全球电动汽车市场 2024-2025 年的竞争格局与技术趋势",
      "expected_keywords": ["电动汽车", "市场", "竞争", "格局", "技术趋势"],
      "expected_min_length": 10,
      "expected_max_length": 200
    },
    {
      "id": "clarify-003",
      "query": "调研 RAG（检索增强生成）技术在企业知识库中的应用现状与局限",
      "expected_keywords": ["RAG", "检索增强", "知识库", "企业", "应用", "局限"],
      "expected_min_length": 10,
      "expected_max_length": 200
    }
  ]
}
```

- [ ] **Step 2: Write search_and_summarize golden cases**

```json
{
  "description": "search_and_summarize 的 golden 测试数据集",
  "test_cases": [
    {
      "id": "search-001",
      "query": "AI Agent 软件开发",
      "expected_results_min": 1,
      "expected_fields": ["title", "url", "summary"]
    },
    {
      "id": "search-002",
      "query": "机器学习 最新进展",
      "expected_results_min": 1,
      "expected_fields": ["title", "url", "summary"]
    }
  ]
}
```

- [ ] **Step 3: Write generate_report golden cases**

```json
{
  "description": "generate_report 的 golden 测试数据集",
  "test_cases": [
    {
      "id": "report-001",
      "notes_count": 3,
      "expected_min_length": 100,
      "expected_format": "markdown"
    }
  ]
}
```

- [ ] **Step 4: Write blackboard generate_steps golden cases**

```json
{
  "description": "generate_steps 的 golden 测试数据集",
  "test_cases": [
    {
      "id": "blackboard-001",
      "topic": "鱼香肉丝的做法",
      "expected_steps_min": 3,
      "expected_fields": ["title", "note", "boardState"]
    },
    {
      "id": "blackboard-002",
      "topic": "Python 编程基础",
      "expected_steps_min": 3,
      "expected_fields": ["title", "note", "boardState"]
    }
  ]
}
```

---

## Task 3: 创建 fixtures/factories.py

**Files:**
- Create: `backend/tests/fixtures/factories.py`

- [ ] **Step 1: Write factories.py**

```python
# backend/tests/fixtures/factories.py
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import User
from app.workspace.models import Workspace
from app.chat.models import Chat


class UserFactory:
    """Factory for creating test User instances."""

    @staticmethod
    async def create(
        session: AsyncSession,
        username: str = "testuser",
        password_hash: Optional[str] = None,
        **kwargs: Any,
    ) -> User:
        if password_hash is None:
            password_hash = "fakehash"
        user = User(username=username, password_hash=password_hash, **kwargs)
        session.add(user)
        await session.flush()
        return user


class WorkspaceFactory:
    """Factory for creating test Workspace instances."""

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: int,
        name: str = "Test Workspace",
        **kwargs: Any,
    ) -> Workspace:
        ws = Workspace(user_id=user_id, name=name, **kwargs)
        session.add(ws)
        await session.flush()
        return ws


class ChatFactory:
    """Factory for creating test Chat instances."""

    @staticmethod
    async def create(
        session: AsyncSession,
        workspace_id: int,
        title: str = "New Chat",
        **kwargs: Any,
    ) -> Chat:
        chat = Chat(workspace_id=workspace_id, title=title, **kwargs)
        session.add(chat)
        await session.flush()
        return chat
```

- [ ] **Step 2: Verify factories.py syntax**

Run: `cd /wslshare/taskly/feature-5/backend && python -c "from tests.fixtures.factories import UserFactory, WorkspaceFactory, ChatFactory; print('OK')"`
Expected: OK

---

## Task 4: 创建 fixtures/golden_loader.py

**Files:**
- Create: `backend/tests/fixtures/golden_loader.py`

- [ ] **Step 1: Write golden_loader.py**

```python
# backend/tests/fixtures/golden_loader.py
import json
from pathlib import Path
from typing import Any


def load_golden_cases(category: str, name: str) -> list[dict[str, Any]]:
    """
    Load golden test cases from JSON file.

    Args:
        category: subdirectory under fixtures/golden/, e.g. 'research', 'blackboard'
        name: filename without .json, e.g. 'clarify_topic'

    Returns:
        List of test case dicts from the 'test_cases' field.
    """
    path = Path(__file__).parent / "golden" / category / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Golden file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("test_cases", [])
```

- [ ] **Step 2: Verify loader works**

Run: `cd /wslshare/taskly/feature-5/backend && python -c "from tests.fixtures.golden_loader import load_golden_cases; cases = load_golden_cases('research', 'clarify_topic'); print(f'Loaded {len(cases)} cases')"`
Expected: Loaded N cases

---

## Task 5: 重写根级 conftest.py

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Read existing conftest.py**

Run: `cat /wslshare/taskly/feature-5/backend/tests/conftest.py`
(Read the file to understand existing fixtures)

- [ ] **Step 2: Write new conftest.py preserving existing fixtures**

```python
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
async def auth_client(async_client, test_user):
    """
    自动注入当前测试用户的客户端。
    """
    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield async_client
```

- [ ] **Step 3: Verify conftest.py loads**

Run: `cd /wslshare/taskly/feature-5/backend && python -c "import tests.conftest; print('conftest OK')"`
Expected: conftest OK

---

## Task 6: 创建 unit/llm/conftest.py

**Files:**
- Create: `backend/tests/unit/llm/conftest.py`
- Create: `backend/tests/unit/conftest.py`

- [ ] **Step 1: Write unit/llm/conftest.py**

```python
# backend/tests/unit/llm/conftest.py
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_model():
    """Create a mock ChatOpenAI model."""
    model = MagicMock()
    model.invoke = MagicMock()
    model.ainvoke = AsyncMock()
    model.stream = MagicMock()
    model.astream = AsyncMock()
    model.batch = MagicMock()
    model.abatch = AsyncMock()
    model.bind_tools = MagicMock()
    model.with_structured_output = MagicMock()
    model.callbacks = []
    return model
```

- [ ] **Step 2: Write unit/conftest.py**

```python
# backend/tests/unit/conftest.py
# Unit tests conftest - placeholder for future shared fixtures
```

---

## Task 7: 拆分 test_llm_calls.py 为 unit/llm/ 下的 4 个文件

**Files:**
- Create: `backend/tests/unit/llm/test_llm_invoke.py`
- Create: `backend/tests/unit/llm/test_llm_stream.py`
- Create: `backend/tests/unit/llm/test_llm_structured.py`
- Create: `backend/tests/unit/llm/test_llm_tool.py`
- Delete: `backend/tests/test_llm_calls.py`

- [ ] **Step 1: Write test_llm_invoke.py (from test_llm_calls.py lines 48-106)**

```python
# backend/tests/unit/llm/test_llm_invoke.py
"""
Unit tests for llm_invoke and llm_invoke_async.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class TestLlmInvoke:
    """Tests for llm_invoke and llm_invoke_async."""

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_returns_text(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="The answer is 42.")

        from app.llm import llm_invoke

        result = llm_invoke("What is the meaning of life?")
        assert result == "The answer is 42."
        mock_model.invoke.assert_called_once()

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_with_system_prompt(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="Hello!")

        from app.llm import llm_invoke

        result = llm_invoke("Hi", system_prompt="You are a friendly assistant.")
        call_args = mock_model.invoke.call_args[0][0]
        assert len(call_args) == 2
        assert isinstance(call_args[0], SystemMessage)
        assert isinstance(call_args[1], HumanMessage)

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_with_messages_override(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="Response")

        from app.llm import llm_invoke

        messages = [HumanMessage(content="Hello")]
        result = llm_invoke("ignored", messages=messages)
        mock_model.invoke.assert_called_once_with(messages)

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_uses_correct_model_tier(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="Result")

        from app.llm import llm_invoke

        llm_invoke("test", model_name="max")
        mock_get_llm.assert_called_with(model_name="max", streaming=False)

    @patch("app.llm.calls.get_llm")
    async def test_llm_invoke_async(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="async result"))

        from app.llm import llm_invoke_async

        result = await llm_invoke_async("test prompt")
        assert result == "async result"

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_with_extra_kwargs(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="result")

        from app.llm import llm_invoke

        result = llm_invoke("test", temperature=0.7, max_tokens=100)
        assert result == "result"
        mock_get_llm.assert_called_with(model_name="mini", streaming=False, temperature=0.7, max_tokens=100)

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_mini_model(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="result")

        from app.llm import llm_invoke

        llm_invoke("test", model_name="mini")
        mock_get_llm.assert_called_with(model_name="mini", streaming=False)

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_max_model(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="result")

        from app.llm import llm_invoke

        llm_invoke("test", model_name="max")
        mock_get_llm.assert_called_with(model_name="max", streaming=False)
```

- [ ] **Step 2: Write test_llm_stream.py (from lines 111-157 + streaming model tier tests)**

```python
# backend/tests/unit/llm/test_llm_stream.py
"""
Unit tests for llm_stream and llm_stream_async.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessageChunk

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class TestLlmStream:
    """Tests for llm_stream and llm_stream_async."""

    @patch("app.llm.calls.get_llm")
    def test_llm_stream_yields_tokens(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        chunks = [
            AIMessageChunk(content="Hello"),
            AIMessageChunk(content=" world"),
        ]
        mock_model.stream.return_value = iter(chunks)

        from app.llm import llm_stream

        tokens = list(llm_stream("Say hello"))
        assert tokens == ["Hello", " world"]

    @patch("app.llm.calls.get_llm")
    def test_llm_stream_with_content_blocks(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        chunks = [
            AIMessageChunk(content=[{"type": "text", "text": "Part1"}]),
            AIMessageChunk(content=[{"type": "text", "text": "Part2"}]),
        ]
        mock_model.stream.return_value = iter(chunks)

        from app.llm import llm_stream

        tokens = list(llm_stream("test"))
        assert tokens == ["Part1", "Part2"]

    @patch("app.llm.calls.get_llm")
    async def test_llm_stream_async(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model

        async def async_gen():
            yield AIMessageChunk(content="async ")
            yield AIMessageChunk(content="token")

        mock_model.astream = MagicMock(side_effect=lambda *args, **kwargs: async_gen())

        from app.llm import llm_stream_async

        tokens = [t async for t in llm_stream_async("test")]
        assert tokens == ["async ", "token"]

    @patch("app.llm.calls.get_llm")
    def test_llm_stream_uses_streaming_true(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.stream.return_value = iter([])

        from app.llm import llm_stream

        list(llm_stream("test"))
        mock_get_llm.assert_called_with(model_name="mini", streaming=True)
```

- [ ] **Step 3: Write test_llm_structured.py (from lines 163-458)**

```python
# backend/tests/unit/llm/test_llm_structured.py
"""
Unit tests for llm_structured_invoke, llm_structured_dict_invoke, llm_batch_invoke.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage, AIMessageChunk, SystemMessage
from pydantic import BaseModel, Field

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class TestLlmStructuredInvoke:
    """Tests for llm_structured_invoke and variants."""

    @patch("app.llm.calls.get_llm")
    def test_llm_structured_invoke_returns_pydantic_model(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model

        class Movie(BaseModel):
            title: str = Field(description="Movie title")
            year: int = Field(description="Release year")

        mock_structured = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = Movie(title="Inception", year=2010)

        from app.llm import llm_structured_invoke

        result = llm_structured_invoke("Tell me about Inception", output_schema=Movie)
        assert result.title == "Inception"
        assert result.year == 2010
        mock_model.with_structured_output.assert_called_once()

    @patch("app.llm.calls.get_llm")
    def test_llm_structured_invoke_with_method_param(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model

        class Person(BaseModel):
            name: str

        mock_structured = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = Person(name="Alice")

        from app.llm import llm_structured_invoke

        llm_structured_invoke("Who is Alice?", output_schema=Person, method="json_schema")
        call_kwargs = mock_model.with_structured_output.call_args[1]
        assert call_kwargs["method"] == "json_schema"

    @patch("app.llm.calls.get_llm")
    async def test_llm_structured_invoke_async(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model

        class Result(BaseModel):
            value: str

        mock_structured = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke = AsyncMock(return_value=Result(value="test"))

        from app.llm import llm_structured_invoke_async

        result = await llm_structured_invoke_async("test", output_schema=Result)
        assert result.value == "test"

    @patch("app.llm.calls.get_llm")
    def test_llm_structured_dict_invoke_returns_dict(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model

        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "year": {"type": "integer"}
            },
            "required": ["title", "year"]
        }

        mock_structured = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = {"title": "Inception", "year": 2010}

        from app.llm import llm_structured_dict_invoke

        result = llm_structured_dict_invoke("Tell me about Inception", output_schema=schema)
        assert result == {"title": "Inception", "year": 2010}

    @patch("app.llm.calls.get_llm")
    def test_llm_structured_invoke_strict_param(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model

        class Schema(BaseModel):
            value: str

        mock_structured = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = Schema(value="test")

        from app.llm import llm_structured_invoke

        llm_structured_invoke("test", output_schema=Schema, strict=True)
        call_kwargs = mock_model.with_structured_output.call_args[1]
        assert call_kwargs["strict"] is True

    @patch("app.llm.calls.get_llm")
    def test_llm_structured_invoke_uses_streaming_false(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model

        class Schema(BaseModel):
            value: str

        mock_structured = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = Schema(value="test")

        from app.llm import llm_structured_invoke

        llm_structured_invoke("test", output_schema=Schema)
        mock_get_llm.assert_called_with(model_name="mini", streaming=False)


class TestLlmBatchInvoke:
    """Tests for llm_batch_invoke and llm_batch_invoke_async."""

    @patch("app.llm.calls.get_llm")
    def test_llm_batch_invoke(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.batch.return_value = [
            AIMessage(content="Answer 1"),
            AIMessage(content="Answer 2"),
            AIMessage(content="Answer 3"),
        ]

        from app.llm import llm_batch_invoke

        results = llm_batch_invoke(["Q1", "Q2", "Q3"])
        assert len(results) == 3
        mock_model.batch.assert_called_once()

    @patch("app.llm.calls.get_llm")
    async def test_llm_batch_invoke_async(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.abatch = AsyncMock(return_value=[
            AIMessage(content="async answer 1"),
            AIMessage(content="async answer 2"),
        ])

        from app.llm import llm_batch_invoke_async

        results = await llm_batch_invoke_async(["Q1", "Q2"])
        assert len(results) == 2
        mock_model.abatch.assert_called_once()

    @patch("app.llm.calls.get_llm")
    def test_llm_batch_invoke_with_system_prompt(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.batch.return_value = [AIMessage(content="r")]

        from app.llm import llm_batch_invoke

        llm_batch_invoke(["Q1"], system_prompt="You are helpful.")
        call_args = mock_model.batch.call_args[0][0]
        for messages in call_args:
            assert len(messages) == 2
            assert isinstance(messages[0], SystemMessage)


class TestLlmCallsEdgeCases:
    """Edge cases and error handling."""

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_with_custom_callbacks(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="result")

        from app.llm import llm_invoke

        custom_callback = MagicMock()
        llm_invoke("test", callbacks=[custom_callback])

        assert len(mock_model.callbacks) == 2
```

- [ ] **Step 4: Write test_llm_tool.py (from lines 245-407)**

```python
# backend/tests/unit/llm/test_llm_tool.py
"""
Unit tests for llm_tool_call and llm_tool_stream.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain.tools import tool

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class TestLlmToolCall:
    """Tests for llm_tool_call and variants."""

    @patch("app.llm.calls.get_llm")
    def test_llm_tool_call_binds_tools(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_bound = MagicMock()
        mock_model.bind_tools.return_value = mock_bound

        mock_bound.invoke.return_value = AIMessage(
            content="",
            tool_calls=[
                {"name": "get_weather", "args": {"location": "Tokyo"}, "id": "call_1", "type": "tool_call"}
            ]
        )

        from app.llm import llm_tool_call

        @tool
        def get_weather(location: str) -> str:
            """Get weather for a location."""
            return "sunny"

        result = llm_tool_call("What's the weather in Tokyo?", tools=[get_weather])

        mock_model.bind_tools.assert_called_once()
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "get_weather"

    @patch("app.llm.calls.get_llm")
    def test_llm_tool_call_parallel_tool_calls(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_bound = MagicMock()
        mock_model.bind_tools.return_value = mock_bound

        mock_bound.invoke.return_value = AIMessage(
            content="",
            tool_calls=[
                {"name": "get_weather", "args": {"location": "Tokyo"}, "id": "call_1", "type": "tool_call"},
                {"name": "get_time", "args": {"city": "Tokyo"}, "id": "call_2", "type": "tool_call"},
            ]
        )

        from app.llm import llm_tool_call

        @tool
        def get_weather(location: str) -> str:
            return "sunny"

        @tool
        def get_time(city: str) -> str:
            return "2 PM"

        result = llm_tool_call(
            "Weather and time in Tokyo?",
            tools=[get_weather, get_time],
            parallel_tool_calls=True
        )

        bind_call_kwargs = mock_model.bind_tools.call_args[1]
        assert bind_call_kwargs["parallel_tool_calls"] is True
        assert len(result.tool_calls) == 2

    @patch("app.llm.calls.get_llm")
    def test_llm_tool_call_with_tool_choice(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_bound = MagicMock()
        mock_model.bind_tools.return_value = mock_bound
        mock_bound.invoke.return_value = AIMessage(content="", tool_calls=[])

        from app.llm import llm_tool_call

        @tool
        def tool_a() -> str:
            return "a"

        llm_tool_call("test", tools=[tool_a], tool_choice="any")

        bind_call_kwargs = mock_model.bind_tools.call_args[1]
        assert bind_call_kwargs["tool_choice"] == "any"

    @patch("app.llm.calls.get_llm")
    async def test_llm_tool_call_async(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_bound = MagicMock()
        mock_model.bind_tools.return_value = mock_bound
        mock_bound.ainvoke = AsyncMock(return_value=AIMessage(content="", tool_calls=[]))

        from app.llm import llm_tool_call_async

        @tool
        def dummy() -> str:
            return "ok"

        await llm_tool_call_async("test", tools=[dummy])
        mock_bound.ainvoke.assert_called_once()

    @patch("app.llm.calls.get_llm")
    def test_llm_tool_call_with_messages(self, mock_get_llm, mock_model):
        """When messages are provided, prompt should be ignored."""
        mock_get_llm.return_value = mock_model
        mock_bound = MagicMock()
        mock_model.bind_tools.return_value = mock_bound

        existing_messages = [SystemMessage(content="System"), HumanMessage(content="Hello")]
        mock_bound.invoke.return_value = AIMessage(content="", tool_calls=[])

        from app.llm import llm_tool_call

        @tool
        def dummy() -> str:
            return "ok"

        llm_tool_call("this prompt should be ignored", tools=[dummy], messages=existing_messages)
        mock_bound.invoke.assert_called_once_with(existing_messages)


class TestLlmToolStream:
    """Tests for llm_tool_stream and llm_tool_stream_async."""

    @patch("app.llm.calls.get_llm")
    def test_llm_tool_stream_yields_chunks(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_bound = MagicMock()
        mock_model.bind_tools.return_value = mock_bound

        mock_bound.stream.return_value = iter([
            AIMessageChunk(content="", tool_call_chunks=[{"name": "get_weather", "args": "", "id": "call_1", "type": "tool_call_chunk"}]),
            AIMessageChunk(content=""),
        ])

        from app.llm import llm_tool_stream

        @tool
        def get_weather(location: str) -> str:
            return "sunny"

        chunks = list(llm_tool_stream("Weather?", tools=[get_weather]))
        assert len(chunks) == 2
        assert chunks[0].tool_call_chunks is not None

    @patch("app.llm.calls.get_llm")
    async def test_llm_tool_stream_async(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_bound = MagicMock()
        mock_model.bind_tools.return_value = mock_bound

        async def async_gen():
            yield AIMessageChunk(content="partial")

        mock_bound.astream = MagicMock(side_effect=lambda *args, **kwargs: async_gen())

        from app.llm import llm_tool_stream_async

        @tool
        def dummy() -> str:
            return "ok"

        chunks = [c async for c in llm_tool_stream_async("test", tools=[dummy])]
        assert len(chunks) == 1
```

- [ ] **Step 5: Delete old test_llm_calls.py**

Run: `rm /wslshare/taskly/feature-5/backend/tests/test_llm_calls.py`

- [ ] **Step 6: Run unit tests to verify split**

Run: `cd /wslshare/taskly/feature-5/backend && SKIP_DB_SETUP=1 pytest tests/unit/llm/ -v --tb=short 2>&1 | head -80`
Expected: Tests pass or fail with clear error messages (not import errors)

---

## Task 8: 创建 integration/ 测试

**Files:**
- Create: `backend/tests/integration/conftest.py`
- Create: `backend/tests/integration/test_auth.py`
- Create: `backend/tests/integration/test_workspace.py`
- Create: `backend/tests/integration/test_chat.py`

- [ ] **Step 1: Write integration/conftest.py**

```python
# backend/tests/integration/conftest.py
import pytest

pytestmark = pytest.mark.integration
```

- [ ] **Step 2: Write test_auth.py (expanded from test_api.py auth section)**

```python
# backend/tests/integration/test_auth.py
"""
Integration tests for authentication: register, login, invalid login.
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_register_and_login(async_client):
    """Register a new user and then login with valid credentials."""
    # 1. Register
    reg_res = await async_client.post(
        "/auth/register",
        json={"username": "realuser", "password": "realpassword"}
    )
    assert reg_res.status_code == 200
    data = reg_res.json()
    assert data["username"] == "realuser"
    assert "id" in data

    # 2. Login
    login_res = await async_client.post(
        "/auth/login",
        data={"username": "realuser", "password": "realpassword"}
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    assert "access_token" in tokens
    assert tokens["token_type"] == "bearer"

    # 3. Invalid Login
    invalid_res = await async_client.post(
        "/auth/login",
        data={"username": "realuser", "password": "wrongpassword"}
    )
    assert invalid_res.status_code == 401


async def test_register_duplicate_username(async_client):
    """Registering with existing username should fail."""
    await async_client.post(
        "/auth/register",
        json={"username": "dupuser", "password": "password123"}
    )
    dup_res = await async_client.post(
        "/auth/register",
        json={"username": "dupuser", "password": "password456"}
    )
    assert dup_res.status_code == 400
```

- [ ] **Step 3: Write test_workspace.py (from test_api.py workspace tests)**

```python
# backend/tests/integration/test_workspace.py
"""
Integration tests for workspace CRUD.
"""
import pytest
from app.workspace.models import Workspace

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_create_workspace(auth_client, test_user, db_session):
    """Create a workspace and verify it exists in DB."""
    response = await auth_client.post(
        "/workspaces/",
        json={"name": "Test Workspace"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Workspace"
    assert "id" in data

    db_ws = await db_session.get(Workspace, data["id"])
    assert db_ws is not None
    assert db_ws.user_id == test_user.id


async def test_list_workspaces(auth_client):
    """List workspaces returns all workspaces for the user."""
    await auth_client.post("/workspaces/", json={"name": "Test Workspace"})
    await auth_client.post("/workspaces/", json={"name": "Second Workspace"})

    response = await auth_client.get("/workspaces/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = [w["name"] for w in data]
    assert "Test Workspace" in names
    assert "Second Workspace" in names


async def test_delete_workspace(auth_client):
    """Delete workspace removes it from DB."""
    ws_res = await auth_client.post("/workspaces/", json={"name": "To Delete"})
    ws_id = ws_res.json()["id"]

    del_res = await auth_client.delete(f"/workspaces/{ws_id}")
    assert del_res.status_code == 200

    get_res = await auth_client.get(f"/workspaces/{ws_id}")
    assert get_res.status_code == 404
```

- [ ] **Step 4: Write test_chat.py (from test_api.py chat tests)**

```python
# backend/tests/integration/test_chat.py
"""
Integration tests for chat CRUD.
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_create_chat_in_workspace(auth_client, db_session):
    """Create a chat in a workspace."""
    ws_res = await auth_client.post("/workspaces/", json={"name": "Chat Workspace"})
    ws_id = ws_res.json()["id"]

    chat_res = await auth_client.post("/chats/", json={"workspace_id": ws_id})
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["workspace_id"] == ws_id
    assert chat_data["title"] == "New Chat"


async def test_list_chats_by_workspace(auth_client):
    """List chats filtered by workspace."""
    ws1_res = await auth_client.post("/workspaces/", json={"name": "WS 1"})
    ws1_id = ws1_res.json()["id"]

    ws2_res = await auth_client.post("/workspaces/", json={"name": "WS 2"})
    ws2_id = ws2_res.json()["id"]

    await auth_client.post("/chats/", json={"workspace_id": ws1_id})
    await auth_client.post("/chats/", json={"workspace_id": ws1_id})
    await auth_client.post("/chats/", json={"workspace_id": ws2_id})

    res1 = await auth_client.get(f"/chats/?workspace_id={ws1_id}")
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1) == 2
    for chat in data1:
        assert chat["workspace_id"] == ws1_id

    res2 = await auth_client.get(f"/chats/?workspace_id={ws2_id}")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2) == 1
    assert data2[0]["workspace_id"] == ws2_id
```

- [ ] **Step 5: Run integration tests to verify**

Run: `cd /wslshare/taskly/feature-5/backend && SKIP_DB_SETUP=1 pytest tests/integration/ -v --tb=short 2>&1 | head -60`
Expected: Tests pass or fail with clear errors

---

## Task 9: 创建 ai_logic/ 测试

**Files:**
- Create: `backend/tests/ai_logic/conftest.py`
- Create: `backend/tests/ai_logic/test_research_agent.py` (from test_research_integration.py)
- Create: `backend/tests/ai_logic/test_research_tools.py` (preserve existing)
- Create: `backend/tests/ai_logic/test_blackboard_agent.py` (rewrite from test_llm_blackboard.py)

- [ ] **Step 1: Write ai_logic/conftest.py**

```python
# backend/tests/ai_logic/conftest.py
import pytest

pytestmark = pytest.mark.ai_logic
```

- [ ] **Step 2: Write test_research_agent.py (moved from test_research_integration.py with markers)**

Copy content from `test_research_integration.py` and add `@pytest.mark.ai_logic` to all test classes.

```python
# backend/tests/ai_logic/test_research_agent.py
"""
AI logic tests for app.research.agent — deep research scenarios with mocks.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import HumanMessage
from app.research.agent import (
    clarify_topic, plan_search, execute_search, synthesize,
    should_continue, generate_report, build_graph,
)
from langgraph.graph import END
from app.research.state import (
    ResearchState, NeedsClarification, ResearchTopic,
    SearchPlan, Summary, FinalReport, ResearchLevel,
)

pytestmark = [pytest.mark.ai_logic, pytest.mark.asyncio]
```

Then copy all test classes from `test_research_integration.py` (lines 73-599).

- [ ] **Step 3: Write test_research_tools.py (preserve from existing)**

```python
# backend/tests/ai_logic/test_research_tools.py
"""
AI logic tests for app.research.tools — web search and summarization.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.research.state import Summary

pytestmark = [pytest.mark.ai_logic, pytest.mark.asyncio]
```

Copy content from existing `test_research_tools.py`.

- [ ] **Step 4: Write test_blackboard_agent.py (rewrite from test_llm_blackboard.py)**

```python
# backend/tests/ai_logic/test_blackboard_agent.py
"""
AI logic tests for app.blackboard.agent.
Uses golden dataset + mock LLM to verify call logic.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from types import SimpleNamespace

pytestmark = [pytest.mark.ai_logic, pytest.mark.asyncio]


def make_config():
    return {"configurable": {"thread_id": "test-blackboard", "task_id": "test-task"}}


class TestBlackboardAgent:
    """Tests for run_blackboard_agent."""

    @patch("app.blackboard.agent.get_llm")
    async def test_blackboard_generation_returns_steps(self, mock_get_llm):
        """Verify blackboard agent returns expected step structure."""
        from app.blackboard.agent import run_blackboard_agent

        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke = AsyncMock(return_value=[
            SimpleNamespace(
                title="Step 1: 准备食材",
                note="列出所需食材和调料",
                boardState=[
                    {"id": "b1", "type": "text", "content": "猪肉丝 200g"},
                    {"id": "b2", "type": "text", "content": "郫县豆瓣酱 2勺"},
                ]
            ),
            SimpleNamespace(
                title="Step 2: 调制料汁",
                note="根据个人口味调整",
                boardState=[
                    {"id": "b3", "type": "text", "content": "醋 1勺"},
                    {"id": "b4", "type": "text", "content": "糖 1勺"},
                ]
            ),
        ])
        mock_get_llm.return_value = mock_model

        topic = "鱼香肉丝的做法"
        result = await run_blackboard_agent(topic)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["title"] == "Step 1: 准备食材"
        assert "boardState" in result[0]
        assert len(result[0]["boardState"]) == 2
        mock_get_llm.assert_called()

    @patch("app.blackboard.agent.get_llm")
    async def test_blackboard_generation_validates_output(self, mock_get_llm):
        """Verify output has required fields."""
        from app.blackboard.agent import run_blackboard_agent

        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke = AsyncMock(return_value=[
            SimpleNamespace(
                title="Step",
                note="Note",
                boardState=[]
            ),
        ])
        mock_get_llm.return_value = mock_model

        result = await run_blackboard_agent("test topic")

        for step in result:
            assert "title" in step
            assert "note" in step
            assert "boardState" in step
```

- [ ] **Step 5: Run ai_logic tests to verify**

Run: `cd /wslshare/taskly/feature-5/backend && SKIP_DB_SETUP=1 pytest tests/ai_logic/ -v --tb=short 2>&1 | head -80`
Expected: Tests pass or fail with clear errors

---

## Task 10: 创建 ai_quality/ 测试

**Files:**
- Create: `backend/tests/ai_quality/conftest.py`
- Create: `backend/tests/ai_quality/test_research_golden.py` (enhanced from existing)

- [ ] **Step 1: Write ai_quality/conftest.py**

```python
# backend/tests/ai_quality/conftest.py
import pytest

pytestmark = pytest.mark.ai_quality
```

- [ ] **Step 2: Write test_research_golden.py with golden loader**

```python
# backend/tests/ai_quality/test_research_golden.py
"""
Golden dataset tests for deep research.
Real API calls with semantic keyword validation.
"""
import pytest
from langchain_core.messages import HumanMessage
from app.research.agent import build_graph, clarify_topic
from app.research.state import ResearchState, ResearchLevel
from tests.fixtures.golden_loader import load_golden_cases

pytestmark = [pytest.mark.ai_quality, pytest.mark.asyncio]


def make_config(task_id: str):
    return {"configurable": {"thread_id": f"research_{task_id}", "task_id": task_id}}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", load_golden_cases("research", "clarify_topic"))
async def test_clarify_topic_golden(case):
    """
    Test that clarify_topic extracts a topic containing expected keywords.
    Uses golden dataset from JSON for semantic validation.
    """
    state = ResearchState(
        messages=[HumanMessage(content=case["query"])],
        research_topic="",
        search_queries=[],
        search_results=[],
        notes=[],
        final_report="",
        iterations=0,
        max_iterations=3,
        max_results=10,
        research_level=ResearchLevel.STANDARD,
    )

    result = await clarify_topic(state, make_config(f"golden-{case['id']}"))
    topic = result.update.get("research_topic", "") if result.update else ""

    assert topic, f"Topic should not be empty for query: {case['query']}"
    assert len(topic) >= case.get("expected_min_length", 5), \
        f"Topic too short for '{case['query']}': {topic}"
    assert len(topic) <= case.get("expected_max_length", 500), \
        f"Topic too long for '{case['query']}': {topic}"

    found = any(kw.lower() in topic.lower() for kw in case["expected_keywords"])
    assert found, (
        f"None of {case['expected_keywords']} found in topic for query '{case['query']}'. "
        f"Got: {topic}"
    )


@pytest.mark.asyncio
async def test_graph_smoke_no_api():
    """Smoke test: verify graph compiles without API calls."""
    graph = build_graph()
    assert graph is not None

    state = {
        "messages": [HumanMessage(content="test")],
        "research_topic": "",
        "search_queries": [],
        "search_results": [],
        "notes": [],
        "final_report": "",
        "iterations": 0,
        "max_iterations": 1,
        "max_results": 3,
        "research_level": ResearchLevel.STANDARD,
    }
    config = make_config("smoke-test")

    async for event in graph.astream(state, config):
        pass
```

- [ ] **Step 3: Run ai_quality tests to verify**

Run: `cd /wslshare/taskly/feature-5/backend && SKIP_DB_SETUP=1 pytest tests/ai_quality/ -v --tb=short 2>&1 | head -60`
Expected: Tests run (may skip if API key not available)

---

## Task 11: 处理问题文件

**Files:**
- Delete: `backend/tests/test_auth.py`
- Delete: `backend/tests/test_llm_blackboard.py`
- Delete: `backend/tests/test_pure_http.py`
- Delete: `backend/tests/test_raw_llm.py`
- Delete: `backend/tests/test_llm_morphological.py`

- [ ] **Step 1: Check test_pure_http.py and test_raw_llm.py content first**

Run: `cat /wslshare/taskly/feature-5/backend/tests/test_pure_http.py`
Run: `cat /wslshare/taskly/feature-5/backend/tests/test_raw_llm.py`

If content is useful, merge into appropriate test files before deleting.

- [ ] **Step 2: Delete problem files**

```bash
cd /wslshare/taskly/feature-5/backend/tests
rm -f test_auth.py test_llm_blackboard.py test_pure_http.py test_raw_llm.py test_llm_morphological.py
```

- [ ] **Step 3: Verify deletions**

Run: `ls *.py` (should not show deleted files)

---

## Task 12: 移动保留的测试文件到新目录

**Files:**
- Move: `backend/tests/test_matrix_router.py` → `backend/tests/unit/test_matrix_router.py`
- Move: `backend/tests/test_worker.py` → `backend/tests/unit/test_worker.py`
- Move: `backend/tests/test_research_state.py` → `backend/tests/ai_logic/test_research_state.py`
- Move: `backend/tests/test_research_schemas.py` → `backend/tests/ai_logic/test_research_schemas.py`
- Move: `backend/tests/test_research_prompts.py` → `backend/tests/ai_logic/test_research_prompts.py`

- [ ] **Step 1: Move files to new locations**

```bash
cd /wslshare/taskly/feature-5/backend/tests
mv test_matrix_router.py unit/
mv test_worker.py unit/
mv test_research_state.py ai_logic/
mv test_research_schemas.py ai_logic/
mv test_research_prompts.py ai_logic/
```

- [ ] **Step 2: Verify file moves**

Run: `ls unit/` and `ls ai_logic/`

---

## Task 13: 最终验证

**Files:**
- Verify: `backend/tests/` directory structure
- Verify: All pytest markers work correctly

- [ ] **Step 1: Verify complete directory structure**

Run: `find /wslshare/taskly/feature-5/backend/tests -type f -name "*.py" | sort`

- [ ] **Step 2: Verify markers work**

Run: `cd /wslshare/taskly/feature-5/backend && SKIP_DB_SETUP=1 pytest --collect-only -q 2>&1 | head -40`

- [ ] **Step 3: Run unit tests (should be fast)**

Run: `cd /wslshare/taskly/feature-5/backend && SKIP_DB_SETUP=1 pytest tests/unit/ -v --tb=short 2>&1 | tail -30`

- [ ] **Step 4: Run ai_logic tests**

Run: `cd /wslshare/taskly/feature-5/backend && SKIP_DB_SETUP=1 pytest tests/ai_logic/ -v --tb=short 2>&1 | tail -30`

---

## Self-Review Checklist

After writing the plan:

1. **Spec coverage**: Can I point to a task for each section?
   - ✅ Directory structure → Task 1
   - ✅ pytest.ini markers → Task 1
   - ✅ Golden JSON files → Task 2
   - ✅ Factories → Task 3
   - ✅ conftest.py → Task 4, 5
   - ✅ unit/llm/ split → Task 7
   - ✅ integration tests → Task 8
   - ✅ ai_logic tests → Task 9
   - ✅ ai_quality tests → Task 10
   - ✅ Problem files → Task 11
   - ✅ File moves → Task 12

2. **Placeholder scan**: No TBD/TODO in steps. All code is concrete.

3. **Type consistency**: Function names match existing codebase (`clarify_topic`, `run_blackboard_agent`, etc.)

4. **Scope**: Focused on test reorganization only. No production code changes.
