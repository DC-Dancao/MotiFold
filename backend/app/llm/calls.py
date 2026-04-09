"""
Centralized LLM call utilities.

Provides three main patterns:
1. Normal invoke - synchronous non-streaming calls
2. Streaming invoke - streaming token output
3. Structured output - schema-constrained responses

Based on LangChain best practices:
- https://plsa.github.io/oss/langchain/models
- https://plsa.github.io/oss/langchain/structured-output
"""

from typing import Any, AsyncIterator, Dict, List, Optional, Type, Union

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, Field

from app.llm.factory import get_llm
from app.llm.logger import CentralLLMLoggerCallbackHandler


# =============================================================================
# Normal (non-streaming) calls
# =============================================================================

def llm_invoke(
    prompt: str,
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    **kwargs,
) -> str:
    """
    Simple non-streaming LLM call, returns text response.

    Args:
        prompt: User message content
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list (overrides prompt)
        **kwargs: Additional model parameters (temperature, etc.)

    Returns:
        Text response from the model

    Example:
        >>> response = llm_invoke("Why do birds sing?", model_name="mini")
        >>> print(response)
    """
    model = get_llm(model_name=model_name, streaming=False, **kwargs)
    callbacks = kwargs.pop("callbacks", [])
    callbacks.append(CentralLLMLoggerCallbackHandler())
    model.callbacks = callbacks

    if messages is not None:
        return model.invoke(messages)

    full_messages: List[BaseMessage] = []
    if system_prompt:
        full_messages.append(SystemMessage(content=system_prompt))
    full_messages.append(HumanMessage(content=prompt))

    response = model.invoke(full_messages)
    return response.content if hasattr(response, "content") else str(response)


async def llm_invoke_async(
    prompt: str,
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    **kwargs,
) -> str:
    """
    Async non-streaming LLM call, returns text response.

    Args:
        prompt: User message content
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        **kwargs: Additional model parameters

    Returns:
        Text response from the model
    """
    model = get_llm(model_name=model_name, streaming=False, **kwargs)
    callbacks = kwargs.pop("callbacks", [])
    callbacks.append(CentralLLMLoggerCallbackHandler())
    model.callbacks = callbacks

    if messages is not None:
        return await model.ainvoke(messages)

    full_messages: List[BaseMessage] = []
    if system_prompt:
        full_messages.append(SystemMessage(content=system_prompt))
    full_messages.append(HumanMessage(content=prompt))

    response = await model.ainvoke(full_messages)
    return response.content if hasattr(response, "content") else str(response)


# =============================================================================
# Streaming calls
# =============================================================================

def llm_stream(
    prompt: str,
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    **kwargs,
) -> AsyncIterator[str]:
    """
    Streaming LLM call, yields tokens as they arrive.

    Args:
        prompt: User message content
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        **kwargs: Additional model parameters

    Yields:
        Text tokens as the model generates them

    Example:
        >>> for token in llm_stream("Write a story about a cat"):
        ...     print(token, end="", flush=True)
    """
    model = get_llm(model_name=model_name, streaming=True, **kwargs)
    callbacks = kwargs.pop("callbacks", [])
    callbacks.append(CentralLLMLoggerCallbackHandler())
    model.callbacks = callbacks

    if messages is not None:
        full_messages = messages
    else:
        full_messages = []
        if system_prompt:
            full_messages.append(SystemMessage(content=system_prompt))
        full_messages.append(HumanMessage(content=prompt))

    for chunk in model.stream(full_messages):
        if hasattr(chunk, "content"):
            if isinstance(chunk.content, list):
                for block in chunk.content:
                    if block.get("type") == "text":
                        yield block.get("text", "")
            elif isinstance(chunk.content, str):
                yield chunk.content
        elif hasattr(chunk, "text"):
            yield chunk.text


async def llm_stream_async(
    prompt: str,
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    **kwargs,
) -> AsyncIterator[str]:
    """
    Async streaming LLM call, yields tokens as they arrive.

    Args:
        prompt: User message content
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        **kwargs: Additional model parameters

    Yields:
        Text tokens as the model generates them
    """
    model = get_llm(model_name=model_name, streaming=True, **kwargs)
    callbacks = kwargs.pop("callbacks", [])
    callbacks.append(CentralLLMLoggerCallbackHandler())
    model.callbacks = callbacks

    if messages is not None:
        full_messages = messages
    else:
        full_messages = []
        if system_prompt:
            full_messages.append(SystemMessage(content=system_prompt))
        full_messages.append(HumanMessage(content=prompt))

    async for chunk in model.astream(full_messages):
        if hasattr(chunk, "content"):
            if isinstance(chunk.content, list):
                for block in chunk.content:
                    if block.get("type") == "text":
                        yield block.get("text", "")
            elif isinstance(chunk.content, str):
                yield chunk.content
        elif hasattr(chunk, "text"):
            yield chunk.text


# =============================================================================
# Structured output calls
# =============================================================================

def llm_structured_invoke(
    prompt: str,
    output_schema: Type[BaseModel],
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    method: str = "json_schema",
    strict: Optional[bool] = None,
    **kwargs,
) -> BaseModel:
    """
    Non-streaming LLM call with structured output (Pydantic model).

    Args:
        prompt: User message content
        output_schema: Pydantic BaseModel subclass for output
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        method: Structured output method ('json_schema' or 'function_calling')
        strict: Enable strict schema adherence (provider-dependent)
        **kwargs: Additional model parameters

    Returns:
        Instance of the output_schema Pydantic model

    Example:
        >>> class Movie(BaseModel):
        ...     title: str = Field(description="Movie title")
        ...     year: int = Field(description="Release year")
        >>>
        >>> result = llm_structured_invoke(
        ...     "Tell me about Inception",
        ...     output_schema=Movie
        ... )
        >>> print(result.title, result.year)
    """
    model = get_llm(model_name=model_name, streaming=False, **kwargs)

    # Build the model with structured output
    model_with_structure = model.with_structured_output(
        output_schema,
        method=method,
        strict=strict,
    )

    if messages is not None:
        return model_with_structure.invoke(messages)

    full_messages: List[BaseMessage] = []
    if system_prompt:
        full_messages.append(SystemMessage(content=system_prompt))
    full_messages.append(HumanMessage(content=prompt))

    return model_with_structure.invoke(full_messages)


async def llm_structured_invoke_async(
    prompt: str,
    output_schema: Type[BaseModel],
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    method: str = "json_schema",
    strict: Optional[bool] = None,
    **kwargs,
) -> BaseModel:
    """
    Async non-streaming LLM call with structured output.

    Args:
        prompt: User message content
        output_schema: Pydantic BaseModel subclass for output
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        method: Structured output method ('json_schema' or 'function_calling')
        strict: Enable strict schema adherence
        **kwargs: Additional model parameters

    Returns:
        Instance of the output_schema Pydantic model
    """
    model = get_llm(model_name=model_name, streaming=False, **kwargs)

    model_with_structure = model.with_structured_output(
        output_schema,
        method=method,
        strict=strict,
    )

    if messages is not None:
        return await model_with_structure.ainvoke(messages)

    full_messages: List[BaseMessage] = []
    if system_prompt:
        full_messages.append(SystemMessage(content=system_prompt))
    full_messages.append(HumanMessage(content=prompt))

    return await model_with_structure.ainvoke(full_messages)


def llm_structured_stream(
    prompt: str,
    output_schema: Type[BaseModel],
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    method: str = "json_schema",
    strict: Optional[bool] = None,
    **kwargs,
) -> AsyncIterator[BaseModel]:
    """
    Streaming LLM call with structured output.

    Note: Streaming with structured output is limited. Most providers don't support
    streaming structured output token-by-token. This method will yield the final
    structured result when complete.

    Args:
        prompt: User message content
        output_schema: Pydantic BaseModel subclass for output
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        method: Structured output method
        strict: Enable strict schema adherence
        **kwargs: Additional model parameters

    Yields:
        The structured output object when complete
    """
    model = get_llm(model_name=model_name, streaming=True, **kwargs)

    model_with_structure = model.with_structured_output(
        output_schema,
        method=method,
        strict=strict,
    )

    if messages is not None:
        full_messages = messages
    else:
        full_messages = []
        if system_prompt:
            full_messages.append(SystemMessage(content=system_prompt))
        full_messages.append(HumanMessage(content=prompt))

    # Collect stream into final result
    # Note: structured output typically doesn't stream partial results
    collected = None
    for chunk in model_with_structure.stream(full_messages):
        collected = chunk
        # For some providers, streaming structured output yields partial results
        # Yield if it's a valid structured object, otherwise continue
        if isinstance(chunk, output_schema):
            yield chunk
            collected = None

    if collected is not None and isinstance(collected, output_schema):
        yield collected


# =============================================================================
# Tool calling
# =============================================================================

def llm_tool_call(
    prompt: str,
    tools: List[Any],
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    tool_choice: Optional[Union[str, dict]] = None,
    parallel_tool_calls: bool = True,
    **kwargs,
) -> Any:
    """
    LLM call with tool(s) bound. Supports multiple tools and parallel calling.

    Args:
        prompt: User message content
        tools: List of LangChain tools (from @tool decorator or Tool class)
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        tool_choice: Force specific tool ('any', 'none', or {'type: 'function', 'function': {...}})
        parallel_tool_calls: Allow parallel tool calls (default True, OpenAI/Anthropic support)
        **kwargs: Additional model parameters

    Returns:
        AIMessage with .tool_calls containing the tool call requests

    Example:
        >>> from langchain.tools import tool
        >>>
        >>> @tool
        >>> def get_weather(location: str) -> str:
        ...     return "sunny in " + location
        >>>
        >>> @tool
        >>> def get_time(city: str) -> str:
        ...     return "2 PM in " + city
        >>>
        >>> response = llm_tool_call(
        ...     "Weather in Tokyo and time there?",
        ...     tools=[get_weather, get_time]
        ... )
        >>> for tc in response.tool_calls:
        ...     print(tc["name"], tc["args"])
    """
    model = get_llm(model_name=model_name, streaming=False, **kwargs)

    # Bind tools to model
    bound = model.bind_tools(tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls)

    if messages is not None:
        return bound.invoke(messages)

    full_messages: List[BaseMessage] = []
    if system_prompt:
        full_messages.append(SystemMessage(content=system_prompt))
    full_messages.append(HumanMessage(content=prompt))

    return bound.invoke(full_messages)


async def llm_tool_call_async(
    prompt: str,
    tools: List[Any],
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    tool_choice: Optional[Union[str, dict]] = None,
    parallel_tool_calls: bool = True,
    **kwargs,
) -> Any:
    """
    Async LLM call with tool(s) bound.

    Args:
        prompt: User message content
        tools: List of LangChain tools
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        tool_choice: Force specific tool
        parallel_tool_calls: Allow parallel tool calls
        **kwargs: Additional model parameters

    Returns:
        AIMessage with .tool_calls
    """
    model = get_llm(model_name=model_name, streaming=False, **kwargs)
    bound = model.bind_tools(tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls)

    if messages is not None:
        return await bound.ainvoke(messages)

    full_messages: List[BaseMessage] = []
    if system_prompt:
        full_messages.append(SystemMessage(content=system_prompt))
    full_messages.append(HumanMessage(content=prompt))

    return await bound.ainvoke(full_messages)


def llm_tool_stream(
    prompt: str,
    tools: List[Any],
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    tool_choice: Optional[Union[str, dict]] = None,
    parallel_tool_calls: bool = True,
    **kwargs,
) -> AsyncIterator[Any]:
    """
    Streaming LLM call with tool(s). Yields chunks including progressive tool call data.

    Tool call chunks arrive progressively - useful for showing partial tool call building.
    Final tool_calls are available on the completed AIMessage.

    Args:
        prompt: User message content
        tools: List of LangChain tools
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        tool_choice: Force specific tool
        parallel_tool_calls: Allow parallel tool calls
        **kwargs: Additional model parameters

    Yields:
        AIMessageChunk objects with .content, .tool_call_chunks

    Example:
        >>> for chunk in llm_tool_stream(
        ...     "What's the weather in Tokyo?",
        ...     tools=[get_weather]
        ... ):
        ...     if chunk.tool_call_chunks:
        ...         for tc in chunk.tool_call_chunks:
        ...             print(f"Partial tool call: {tc}")
    """
    model = get_llm(model_name=model_name, streaming=True, **kwargs)
    bound = model.bind_tools(tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls)

    if messages is not None:
        full_messages = messages
    else:
        full_messages = []
        if system_prompt:
            full_messages.append(SystemMessage(content=system_prompt))
        full_messages.append(HumanMessage(content=prompt))

    for chunk in bound.stream(full_messages):
        yield chunk


async def llm_tool_stream_async(
    prompt: str,
    tools: List[Any],
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    tool_choice: Optional[Union[str, dict]] = None,
    parallel_tool_calls: bool = True,
    **kwargs,
) -> AsyncIterator[Any]:
    """
    Async streaming LLM call with tool(s).

    Args:
        prompt: User message content
        tools: List of LangChain tools
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        tool_choice: Force specific tool
        parallel_tool_calls: Allow parallel tool calls
        **kwargs: Additional model parameters

    Yields:
        AIMessageChunk objects
    """
    model = get_llm(model_name=model_name, streaming=True, **kwargs)
    bound = model.bind_tools(tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls)

    if messages is not None:
        full_messages = messages
    else:
        full_messages = []
        if system_prompt:
            full_messages.append(SystemMessage(content=system_prompt))
        full_messages.append(HumanMessage(content=prompt))

    async for chunk in bound.astream(full_messages):
        yield chunk


# =============================================================================
# TypedDict support (alternative to Pydantic)
# =============================================================================

def llm_structured_dict_invoke(
    prompt: str,
    output_schema: Union[Dict[str, Any], str],
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    messages: Optional[List[BaseMessage]] = None,
    method: str = "json_schema",
    **kwargs,
) -> Dict[str, Any]:
    """
    Non-streaming LLM call with JSON Schema structured output (returns dict).

    Use this when you need dict output instead of Pydantic model instance.

    Args:
        prompt: User message content
        output_schema: JSON Schema dict or "json_schema" string for simple output
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        messages: Optional pre-built message list
        method: Structured output method
        **kwargs: Additional model parameters

    Returns:
        Dict matching the output schema

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "title": {"type": "string"},
        ...         "year": {"type": "integer"}
        ...     },
        ...     "required": ["title", "year"]
        ... }
        >>> result = llm_structured_dict_invoke("Tell me about Inception", schema)
    """
    model = get_llm(model_name=model_name, streaming=False, **kwargs)

    model_with_structure = model.with_structured_output(output_schema, method=method)

    if messages is not None:
        full_messages = messages
    else:
        full_messages = []
        if system_prompt:
            full_messages.append(SystemMessage(content=system_prompt))
        full_messages.append(HumanMessage(content=prompt))

    return model_with_structure.invoke(full_messages)


# =============================================================================
# Batch calls
# =============================================================================

def llm_batch_invoke(
    prompts: List[str],
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    **kwargs,
) -> List[str]:
    """
    Batch multiple non-streaming LLM calls for efficiency.

    Args:
        prompts: List of user message prompts
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message shared across calls
        **kwargs: Additional model parameters

    Returns:
        List of text responses

    Example:
        >>> responses = llm_batch_invoke([
        ...     "What is 2+2?",
        ...     "What is 3+3?",
        ...     "What is 4+4?"
        ... ])
    """
    model = get_llm(model_name=model_name, streaming=False, **kwargs)
    callbacks = kwargs.pop("callbacks", [])
    callbacks.append(CentralLLMLoggerCallbackHandler())
    model.callbacks = callbacks

    messages_list = []
    for prompt in prompts:
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        messages_list.append(messages)

    return [
        r.content if hasattr(r, "content") else str(r)
        for r in model.batch(messages_list)
    ]


async def llm_batch_invoke_async(
    prompts: List[str],
    model_name: str = "mini",
    system_prompt: Optional[str] = None,
    max_concurrency: int = 5,
    **kwargs,
) -> List[str]:
    """
    Async batch multiple non-streaming LLM calls with concurrency control.

    Args:
        prompts: List of user message prompts
        model_name: Model tier ('max', 'pro', 'mini')
        system_prompt: Optional system message
        max_concurrency: Max parallel calls (default 5)
        **kwargs: Additional model parameters

    Returns:
        List of text responses
    """
    from langchain_core.runnables import RunnableConfig

    model = get_llm(model_name=model_name, streaming=False, **kwargs)
    callbacks = kwargs.pop("callbacks", [])
    callbacks.append(CentralLLMLoggerCallbackHandler())
    model.callbacks = callbacks

    messages_list = []
    for prompt in prompts:
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        messages_list.append(messages)

    config = RunnableConfig(max_concurrency=max_concurrency)
    return [
        r.content if hasattr(r, "content") else str(r)
        for r in await model.abatch(messages_list, config=config)
    ]
