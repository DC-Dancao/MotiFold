import logging
import os
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.messages import BaseMessage

from app.core.config import settings

# Determine if logging is enabled
LLM_LOGGING_ENABLED = getattr(settings, "LLM_LOGGING_ENABLED", True)

# Setup centralized logger for LLM
llm_logger = logging.getLogger("llm_central_logger")

# Set log level from settings
llm_log_level = getattr(settings, "LLM_LOG_LEVEL", "INFO")
llm_logger.setLevel(getattr(logging, llm_log_level.upper(), logging.INFO))

# Only add handlers and set up logging if enabled
if LLM_LOGGING_ENABLED:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Use RotatingFileHandler for log rotation (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "llm.log"),
        encoding="utf-8",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    console_handler = logging.StreamHandler()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    llm_logger.addHandler(file_handler)
    llm_logger.addHandler(console_handler)


class CentralLLMLoggerCallbackHandler(BaseCallbackHandler):
    """Callback handler that logs LLM inputs, outputs, tokens, and execution time."""

    def __init__(self):
        super().__init__()
        self.start_times: Dict[UUID, float] = {}

    def _is_logging_enabled(self) -> bool:
        """Check if logging is enabled via settings."""
        return getattr(settings, "LLM_LOGGING_ENABLED", True) and llm_logger.level != logging.CRITICAL + 1

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM starts running."""
        if not self._is_logging_enabled():
            return
        self.start_times[run_id] = time.time()
        model_name = kwargs.get("invocation_params", {}).get("model_name", "Unknown Model")
        llm_logger.info(f"[LLM START] run_id: {run_id} | model: {model_name} | prompts: {prompts}")

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Run when Chat Model starts running."""
        if not self._is_logging_enabled():
            return
        self.start_times[run_id] = time.time()
        model_name = kwargs.get("invocation_params", {}).get("model_name", "Unknown Model")

        formatted_messages = []
        for msg_list in messages:
            msg_str = [{"role": m.type, "content": m.content} for m in msg_list]
            formatted_messages.append(msg_str)

        llm_logger.info(f"[LLM START] run_id: {run_id} | model: {model_name} | messages: {formatted_messages}")

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM ends running."""
        if not self._is_logging_enabled():
            return
        elapsed_time = time.time() - self.start_times.pop(run_id, time.time())

        # Extract token usage if available
        token_usage = {}
        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]

        # Extract generations
        generations = []
        for gen_list in response.generations:
            gen_texts = []
            for g in gen_list:
                text = g.text
                # If using structured output/tool calls, text might be empty
                if hasattr(g, 'message'):
                    message = g.message
                    tool_calls = None
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        tool_calls = message.tool_calls
                    elif hasattr(message, 'additional_kwargs') and 'tool_calls' in message.additional_kwargs:
                        tool_calls = message.additional_kwargs['tool_calls']
                    elif hasattr(message, 'additional_kwargs') and 'function_call' in message.additional_kwargs:
                        tool_calls = message.additional_kwargs['function_call']

                    if tool_calls:
                        if text:
                            text = {"text": text, "tool_calls": tool_calls}
                        else:
                            text = {"tool_calls": tool_calls}
                gen_texts.append(text)
            generations.append(gen_texts)

        llm_logger.info(
            f"[LLM END] run_id: {run_id} | time: {elapsed_time:.3f}s | "
            f"tokens: {token_usage} | outputs: {generations}"
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM errors."""
        if not self._is_logging_enabled():
            return
        elapsed_time = time.time() - self.start_times.pop(run_id, time.time())
        llm_logger.error(f"[LLM ERROR] run_id: {run_id} | time: {elapsed_time:.3f}s | error: {str(error)}")
