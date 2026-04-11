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
