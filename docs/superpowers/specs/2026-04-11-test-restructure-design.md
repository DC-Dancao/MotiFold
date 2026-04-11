# 测试重构设计方案

## 概述

对 `backend/tests/` 目录进行全面重构，建立清晰的测试分层、模块化 fixtures 和 Golden Dataset 管理规范。

**优先级**: 可维护性 > 覆盖率 > 质量 > CI/CD

**日期**: 2026-04-11

---

## 目标

1. 建立清晰的测试分层架构
2. 实现模块化 fixtures + 工厂模式
3. 引入 Golden Dataset 管理 AI 测试
4. 拆分过大的测试文件
5. 修复/删除无效测试文件

---

## 测试分层架构

### 分层定义

| Layer | Marker | 运行方式 | 说明 |
|-------|--------|----------|------|
| Unit | `unit` | `pytest -m unit` | Mock，<100ms，CI 默认 |
| Integration | `integration` | `pytest -m integration` | 真实 DB，CI 可选 |
| AI Logic | `ai_logic` | `pytest -m ai_logic` | Golden dataset，mock LLM |
| AI Quality | `ai_quality` | `pytest -m ai_quality` | 真实 API，需手动触发 |

### CI 运行策略

```bash
# 快速测试（CI 默认）
pytest -m "not ai_quality" -v

# 完整测试（含 AI 质量）
pytest -v

# 只跑 AI 逻辑
pytest -m ai_logic -v
```

### pytest.ini 配置

```ini
[pytest]
markers =
    unit: 传统单元测试，mock，快速
    integration: 集成测试，真实 DB
    ai_logic: AI 逻辑测试，golden dataset + mock LLM
    ai_quality: AI 质量测试，真实 API，手动触发
asyncio_mode = auto
```

---

## 目录结构

```
backend/tests/
├── conftest.py                         # 通用 fixtures
├── pytest.ini                          # pytest 配置 + markers
├── fixtures/
│   ├── __init__.py
│   ├── factories.py                    # 测试数据工厂
│   └── golden/                        # Golden dataset
│       ├── research/
│       │   ├── clarify_topic.json
│       │   ├── search_and_summarize.json
│       │   └── generate_report.json
│       └── blackboard/
│           └── generate_steps.json
├── unit/                              # 传统单元测试
│   ├── __init__.py
│   ├── conftest.py                    # 通用 unit fixtures
│   ├── test_matrix_router.py          # [保留] matrix service 逻辑
│   ├── test_worker.py                 # [保留] worker 逻辑
│   └── llm/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_llm_invoke.py         # [拆分] llm_invoke / llm_invoke_async
│       ├── test_llm_stream.py         # [拆分] llm_stream / llm_stream_async
│       ├── test_llm_structured.py     # [拆分] llm_structured_* / llm_batch_*
│       └── test_llm_tool.py           # [拆分] llm_tool_call / llm_tool_stream
├── integration/                       # 集成测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py                   # [重写] 注册/登录/权限
│   ├── test_workspace.py              # [扩展] workspace CRUD
│   └── test_chat.py                   # [新增] chat CRUD
├── ai_logic/                          # AI 逻辑测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_research_agent.py         # [保留/增强] graph + state machine
│   ├── test_research_tools.py         # [保留] tools 函数逻辑
│   ├── test_research_state.py         # [扩展] state 边界条件
│   └── test_blackboard_agent.py       # [重写] blackboard agent + 断言
└── ai_quality/                        # AI 质量测试
    ├── __init__.py
    ├── conftest.py
    └── test_research_golden.py        # [增强] golden dataset + 语义检查
```

---

## 问题文件处理

| 原文件 | 处理方式 | 原因 |
|--------|----------|------|
| `test_auth.py` | **删除**，内容合并到 `integration/test_auth.py` | 完全为空 |
| `test_llm_blackboard.py` | **删除**，重写为 `ai_logic/test_blackboard_agent.py` | 无断言 |
| `test_pure_http.py` | **删除**，检查后合并到相关测试 | 1KB，内容待定 |
| `test_raw_llm.py` | **删除**，合并到 `unit/llm/test_llm_invoke.py` | 内容待定 |
| `test_llm_morphological.py` | **删除**，合并到 `test_matrix_router.py` | 内容少 |
| `test_llm_calls.py` | **拆分** 为 `unit/llm/` 下的 4 个文件 | 24KB，过大 |

---

## Golden Dataset 规范

### 文件格式

```json
{
  "description": "clarify_topic 的 golden 测试数据集",
  "test_cases": [
    {
      "id": "research-clarify-001",
      "query": "研究 AI Agent 在软件开发中的最新进展和面临的挑战",
      "expected_keywords": ["AI Agent", "软件", "进展", "挑战", "自主"],
      "expected_min_length": 10,
      "expected_max_length": 200,
      "metadata": {
        "complexity": "high",
        "adversarial": false
      }
    }
  ]
}
```

### 加载方式

```python
import json
from pathlib import Path

def load_golden_cases(category: str, name: str) -> list[dict]:
    path = Path(__file__).parent.parent / "fixtures" / "golden" / category / f"{name}.json"
    with open(path) as f:
        data = json.load(f)
    return data["test_cases"]
```

---

## Fixture 工厂模式

### 基础工厂

```python
# tests/fixtures/factories.py
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import User
from app.workspace.models import Workspace
from app.chat.models import Chat

class UserFactory:
    @staticmethod
    async def create(
        session: AsyncSession,
        username: str = "testuser",
        **kwargs: Any
    ) -> User:
        user = User(username=username, **kwargs)
        session.add(user)
        await session.flush()
        return user

class WorkspaceFactory:
    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: int,
        name: str = "Test Workspace",
        **kwargs: Any
    ) -> Workspace:
        ws = Workspace(user_id=user_id, name=name, **kwargs)
        session.add(ws)
        await session.flush()
        return ws

class ChatFactory:
    @staticmethod
    async def create(
        session: AsyncSession,
        workspace_id: int,
        title: str = "New Chat",
        **kwargs: Any
    ) -> Chat:
        chat = Chat(workspace_id=workspace_id, title=title, **kwargs)
        session.add(chat)
        await session.flush()
        return chat
```

### conftest.py 重构

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from typing import AsyncGenerator

# 导入工厂
from tests.fixtures.factories import UserFactory, WorkspaceFactory, ChatFactory

@pytest.fixture
def user_factory():
    return UserFactory

@pytest.fixture
def workspace_factory():
    return WorkspaceFactory

@pytest.fixture
def chat_factory():
    return ChatFactory

# 保留原有的 db_session, async_client, auth_client
# ...
```

---

## AI 逻辑测试规范

### Mock LLM 固定响应

```python
class FakeStructuredLLM:
    """用于 AI 逻辑测试的固定响应 mock。"""
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        # 验证调用参数
        assert len(messages) >= 1
        return self.payload
```

### Golden 语义检查

```python
@pytest.mark.asyncio
@pytest.mark.ai_logic
@pytest.mark.parametrize("case", load_golden_cases("research", "clarify_topic"))
async def test_clarify_topic_golden(case, db_session):
    result = await clarify_topic(state_from_query(case["query"]), config)

    # 长度检查
    topic = result.update.get("research_topic", "")
    assert len(topic) >= case["expected_min_length"]
    assert len(topic) <= case["expected_max_length"]

    # 关键词存在检查
    found = any(kw.lower() in topic.lower() for kw in case["expected_keywords"])
    assert found, f"None of {case['expected_keywords']} found in: {topic}"
```

---

## 实现步骤

1. [ ] 创建目录结构 `fixtures/`, `unit/`, `integration/`, `ai_logic/`, `ai_quality/`
2. [ ] 创建 `pytest.ini` 配置 markers
3. [ ] 重写 `conftest.py` — 通用 fixtures
4. [ ] 创建 `fixtures/factories.py` — 工厂类
5. [ ] 创建 Golden dataset JSON 文件
6. [ ] 删除问题文件并重写
7. [ ] 拆分 `test_llm_calls.py` 为 `unit/llm/` 下的 4 个文件
8. [ ] 重写 `ai_logic/test_blackboard_agent.py`
9. [ ] 增强 `ai_quality/test_research_golden.py`
10. [ ] 添加缺失的 integration 测试
11. [ ] 验证所有 markers 运行正常

---

## 验收标准

1. 所有测试文件有有效断言（非空测试）
2. `pytest -m "not ai_quality"` 在 30 秒内完成
3. Golden dataset 覆盖所有 AI agent 入口
4. 每个模块至少有一个 integration 测试
5. 无重复测试逻辑（合并小文件）
