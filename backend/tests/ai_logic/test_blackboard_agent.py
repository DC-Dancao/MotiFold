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
