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

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_with_custom_callbacks(self, mock_get_llm, mock_model):
        """Edge case: custom callbacks are preserved alongside CentralLLMLoggerCallbackHandler."""
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="result")

        from app.llm import llm_invoke

        custom_callback = MagicMock()
        llm_invoke("test", callbacks=[custom_callback])

        assert len(mock_model.callbacks) == 2
