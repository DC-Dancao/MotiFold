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
