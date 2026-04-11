from app.core.config import settings
from app.llm.logger import CentralLLMLoggerCallbackHandler

def get_llm(model_name: str = None, streaming: bool = False, **kwargs):
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

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL if settings.OPENAI_BASE_URL else None,
        streaming=streaming,
        callbacks=callbacks,
        **kwargs
    )
