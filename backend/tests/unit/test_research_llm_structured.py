# backend/tests/unit/test_research_llm_structured.py
"""
Unit tests for app.research.agent._llm_structured — verifies that user content
is properly passed as HumanMessage (not empty).
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from app.research.agent import _llm_structured


pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class TestLlmStructuredUserMessage:
    """Verifies _llm_structured correctly includes/excludes HumanMessage based on user content."""

    @patch("app.research.agent.get_llm")
    async def test_user_content_becomes_human_message(self, mock_get_llm):
        """When user is non-empty, messages list includes both SystemMessage and HumanMessage."""
        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_retry = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.with_retry.return_value = mock_retry

        class Result(BaseModel):
            value: str = Field(default="test")

        mock_retry.ainvoke = AsyncMock(return_value=Result(value="ok"))
        mock_get_llm.return_value = mock_model

        system = "You are a helpful assistant."
        user = "What is 2+2?"

        await _llm_structured("pro", Result, system, user)

        # Verify ainvoke was called with 2 messages
        call_args = mock_retry.ainvoke.call_args
        messages_passed = call_args[0][0]

        assert len(messages_passed) == 2
        assert isinstance(messages_passed[0], SystemMessage)
        assert messages_passed[0].content == system
        assert isinstance(messages_passed[1], HumanMessage)
        assert messages_passed[1].content == user

    @patch("app.research.agent.get_llm")
    async def test_empty_user_skips_human_message(self, mock_get_llm):
        """When user is empty string, only SystemMessage is passed (no empty HumanMessage)."""
        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_retry = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        mock_structured.with_retry.return_value = mock_retry

        class Result(BaseModel):
            value: str = Field(default="test")

        mock_retry.ainvoke = AsyncMock(return_value=Result(value="ok"))
        mock_get_llm.return_value = mock_model

        system = "You are a helpful assistant."
        user = ""

        await _llm_structured("pro", Result, system, user)

        # Verify only SystemMessage was passed
        call_args = mock_retry.ainvoke.call_args
        messages_passed = call_args[0][0]

        assert len(messages_passed) == 1
        assert isinstance(messages_passed[0], SystemMessage)
        assert messages_passed[0].content == system
