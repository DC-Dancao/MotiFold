# backend/tests/unit/llm/test_llm_structured.py
"""
Unit tests for llm_structured_invoke, llm_structured_dict_invoke, llm_batch_invoke.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage, SystemMessage
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
