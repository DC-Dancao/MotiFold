from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.llm.logger import CentralLLMLoggerCallbackHandler

# Centralized LLM calls
from app.llm.calls import (
    llm_invoke,
    llm_invoke_async,
    llm_stream,
    llm_stream_async,
    llm_structured_invoke,
    llm_structured_invoke_async,
    llm_structured_stream,
    llm_structured_dict_invoke,
    llm_batch_invoke,
    llm_batch_invoke_async,
    # Tool calling
    llm_tool_call,
    llm_tool_call_async,
    llm_tool_stream,
    llm_tool_stream_async,
)

def get_llm(model_name: str = None, streaming: bool = False, **kwargs) -> ChatOpenAI:
    """
    Central interface to instantiate ChatOpenAI models.
    Supports passing shorthand names ('max', 'pro', 'mini') or specific model strings.
    """
    if model_name == "max":
        model_name = settings.OPENAI_MODEL_MAX
    elif model_name == "pro":
        model_name = settings.OPENAI_MODEL_PRO
    elif model_name == "mini" or model_name is None:
        model_name = settings.OPENAI_MODEL_MINI

    # Retrieve or initialize callbacks
    callbacks = kwargs.pop("callbacks", [])
    callbacks.append(CentralLLMLoggerCallbackHandler())

    # Ensure token usage is included for streaming
    if streaming:
        model_kwargs = kwargs.get("model_kwargs", {})
        if "stream_options" not in model_kwargs:
            model_kwargs["stream_options"] = {"include_usage": True}
        kwargs["model_kwargs"] = model_kwargs

    return ChatOpenAI(
        model=model_name,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL if settings.OPENAI_BASE_URL else None,
        streaming=streaming,
        callbacks=callbacks,
        **kwargs
    )


__all__ = [
    "get_llm",
    "CentralLLMLoggerCallbackHandler",
    "llm_invoke",
    "llm_invoke_async",
    "llm_stream",
    "llm_stream_async",
    "llm_structured_invoke",
    "llm_structured_invoke_async",
    "llm_structured_stream",
    "llm_structured_dict_invoke",
    "llm_batch_invoke",
    "llm_batch_invoke_async",
    # Tool calling
    "llm_tool_call",
    "llm_tool_call_async",
    "llm_tool_stream",
    "llm_tool_stream_async",
]
