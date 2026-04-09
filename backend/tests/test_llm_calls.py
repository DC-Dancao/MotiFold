"""
Tests for centralized LLM call utilities (app.llm.calls).

Covers:
- llm_invoke / llm_invoke_async
- llm_stream / llm_stream_async
- llm_structured_invoke / llm_structured_invoke_async
- llm_structured_dict_invoke
- llm_batch_invoke / llm_batch_invoke_async
- llm_tool_call / llm_tool_call_async
- llm_tool_stream / llm_tool_stream_async
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Normal invoke tests
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Streaming tests
# --------------------------------------------------------------------------

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

        # astream must be reassigned after each call since async generators are single-use
        mock_model.astream = MagicMock(side_effect=lambda *args, **kwargs: async_gen())

        from app.llm import llm_stream_async

        tokens = [t async for t in llm_stream_async("test")]
        assert tokens == ["async ", "token"]


# --------------------------------------------------------------------------
# Structured output tests
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Tool calling tests
# --------------------------------------------------------------------------

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
        from langchain.tools import tool

        @tool
        def get_weather(location: str) -> str:
            """Get weather for a location."""
            return "sunny"

        @tool
        def get_time(city: str) -> str:
            """Get the current time for a city."""
            return "2 PM"

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
        from langchain.tools import tool

        @tool
        def get_weather(location: str) -> str:
            """Get weather for a location."""
            return "sunny"

        @tool
        def get_time(city: str) -> str:
            """Get the current time for a city."""
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
        from langchain.tools import tool

        @tool
        def tool_a() -> str:
            """A dummy tool for testing."""
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
        from langchain.tools import tool

        @tool
        def dummy() -> str:
            """A dummy tool for testing."""
            return "ok"

        await llm_tool_call_async("test", tools=[dummy])
        mock_bound.ainvoke.assert_called_once()


# --------------------------------------------------------------------------
# Tool streaming tests
# --------------------------------------------------------------------------

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
        from langchain.tools import tool

        @tool
        def get_weather(location: str) -> str:
            """Get weather for a location."""
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
        from langchain.tools import tool

        @tool
        def dummy() -> str:
            """A dummy tool for testing."""
            return "ok"

        chunks = [c async for c in llm_tool_stream_async("test", tools=[dummy])]
        assert len(chunks) == 1


# --------------------------------------------------------------------------
# Batch tests
# --------------------------------------------------------------------------

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
        # Each batch item should have system + human message
        for messages in call_args:
            assert len(messages) == 2
            assert isinstance(messages[0], SystemMessage)


# --------------------------------------------------------------------------
# Integration-style tests (require actual model or full mock)
# --------------------------------------------------------------------------

class TestLlmCallsEdgeCases:
    """Edge cases and error handling."""

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_with_extra_kwargs(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="result")

        from app.llm import llm_invoke

        # Should not raise, extra kwargs should be passed to get_llm
        result = llm_invoke("test", temperature=0.7, max_tokens=100)
        assert result == "result"
        mock_get_llm.assert_called_with(model_name="mini", streaming=False, temperature=0.7, max_tokens=100)

    @patch("app.llm.calls.get_llm")
    def test_llm_invoke_with_custom_callbacks(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="result")

        from app.llm import llm_invoke

        custom_callback = MagicMock()
        llm_invoke("test", callbacks=[custom_callback])

        # Custom callback should be preserved alongside CentralLLMLoggerCallbackHandler
        assert len(mock_model.callbacks) == 2  # custom + CentralLLMLoggerCallbackHandler

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
    def test_llm_tool_call_with_messages(self, mock_get_llm, mock_model):
        """When messages are provided, prompt should be ignored."""
        mock_get_llm.return_value = mock_model
        mock_bound = MagicMock()
        mock_model.bind_tools.return_value = mock_bound

        existing_messages = [SystemMessage(content="System"), HumanMessage(content="Hello")]
        mock_bound.invoke.return_value = AIMessage(content="", tool_calls=[])

        from app.llm import llm_tool_call
        from langchain.tools import tool

        @tool
        def dummy() -> str:
            """A dummy tool for testing."""
            return "ok"

        llm_tool_call("this prompt should be ignored", tools=[dummy], messages=existing_messages)
        mock_bound.invoke.assert_called_once_with(existing_messages)


# --------------------------------------------------------------------------
# Model tier tests
# --------------------------------------------------------------------------

class TestModelTiers:
    """Verify correct model tier is passed to get_llm."""

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
    def test_llm_stream_uses_streaming_true(self, mock_get_llm, mock_model):
        mock_get_llm.return_value = mock_model
        mock_model.stream.return_value = iter([])

        from app.llm import llm_stream

        list(llm_stream("test"))
        mock_get_llm.assert_called_with(model_name="mini", streaming=True)

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


# --------------------------------------------------------------------------
# Real LLM integration tests (no mocking)
# --------------------------------------------------------------------------


class TestLlmRealCalls:
    """Real LLM API integration tests. Require OPENAI_API_KEY and OPENAI_BASE_URL env vars."""

    async def test_llm_invoke_async_real(self):
        """Real async invoke returns a non-empty string."""
        from app.llm import llm_invoke_async

        result = await llm_invoke_async("Reply with exactly 3 words: hi")
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    async def test_llm_stream_async_real(self):
        """Real async streaming yields string tokens."""
        from app.llm import llm_stream_async

        tokens = [t async for t in llm_stream_async("Say 'one two three'")]
        assert len(tokens) >= 1
        full = "".join(tokens)
        assert len(full.strip()) > 0

    async def test_llm_structured_invoke_real(self):
        """Real structured invoke returns a valid Pydantic model."""
        from app.llm import llm_structured_invoke

        class Reply(BaseModel):
            words: int
            text: str

        result = llm_structured_invoke(
            'Answer with a JSON object containing {"words": 3, "text": "hello world"}. Return only the JSON.',
            output_schema=Reply,
        )
        assert isinstance(result, Reply)
        assert isinstance(result.words, int)
        assert isinstance(result.text, str)

    async def test_llm_structured_invoke_real_function_calling(self):
        """Real structured invoke using function_calling method."""
        from app.llm import llm_structured_invoke

        class Reply(BaseModel):
            words: int
            text: str

        result = llm_structured_invoke(
            'Answer with a JSON object containing {"words": 3, "text": "hello world"}. Return only the JSON.',
            output_schema=Reply,
            method="function_calling",
        )
        assert isinstance(result, Reply)
        assert isinstance(result.words, int)
        assert isinstance(result.text, str)

    async def test_llm_batch_invoke_real(self):
        """Real batch invoke returns a list with correct count."""
        from app.llm import llm_batch_invoke_async

        results = await llm_batch_invoke_async(["Reply A", "Reply B"])
        assert len(results) == 2
        assert all(isinstance(r, str) and len(r.strip()) > 0 for r in results)
