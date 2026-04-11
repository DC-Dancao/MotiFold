# backend/tests/unit/llm/test_llm_tool.py
"""
Unit tests for llm_tool_call and llm_tool_stream.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
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
