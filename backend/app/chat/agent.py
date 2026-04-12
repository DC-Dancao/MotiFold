from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from pydantic import BaseModel, Field
from typing import Callable, List, Literal

from app.llm.factory import get_llm
from app.llm.checkpointer import get_checkpointer
from app.core.config import settings

class RouterDecision(BaseModel):
    tags: List[Literal[
        "qa", "rewrite", "translation", "summary", "creative", 
        "reasoning", "coding", "analysis", "agentic", "high_risk"
    ]] = Field(description="List of task tags identified from the input")
    complexity_score: int = Field(ge=0, le=5, description="Complexity score from 0 to 5")
    context_score: int = Field(ge=0, le=5, description="Context dependency score from 0 to 5")
    risk_score: int = Field(ge=0, le=5, description="Risk score from 0 to 5")
    latency_priority: int = Field(ge=0, le=5, description="Latency priority score from 0 to 5")
    recommended_model: Literal["max", "pro", "mini"] = Field(description="The recommended model based on the scores and tags")

class DynamicModelMiddleware(AgentMiddleware):
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable,
    ) -> ModelResponse:
        user_input = request.messages[-1].content if request.messages else ""
        
        # Truncate input: keep first 50 and last 50 chars
        if len(user_input) > 100:
            truncated_input = user_input[:50] + " ... " + user_input[-50:]
        else:
            truncated_input = user_input
            
        # Call mini model to route
        router_llm = get_llm(model_name=settings.OPENAI_MODEL_MINI, streaming=False).with_structured_output(RouterDecision, method="json_schema", strict=True)
        
        system_prompt = (
            "Analyze the user's input and provide a routing decision.\n"
            "Step 1: Identify tags from [qa, rewrite, translation, summary, creative, reasoning, coding, analysis, agentic, high_risk].\n"
            "Step 2: Score from 0-5 for complexity_score, context_score, risk_score, latency_priority.\n"
            "Step 3: Recommend a model (max, pro, mini) based on the analysis."
        )
        
        try:
            decision = await router_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Input draft: {truncated_input}")
            ])
            recommended = decision.recommended_model
        except Exception:
            recommended = "mini"
        
        llm = get_llm(model_name=recommended, streaming=True)
        return await handler(request.override(model=llm))

default_llm = get_llm(model_name=settings.OPENAI_MODEL_MINI, streaming=True)

def get_workflow(checkpointer=None, model_override: str = None):
    """
    Create agent workflow.

    Args:
        checkpointer: LangGraph checkpointer for state persistence
        model_override: Specific model to use ("mini", "pro", "max") or None/"auto" for dynamic routing
    """
    # If specific model requested, use it directly without middleware
    if model_override and model_override != "auto":
        llm = get_llm(model_name=model_override, streaming=True)
        return create_agent(
            model=llm,
            tools=[],
            checkpointer=checkpointer
        )

    # Otherwise use dynamic routing middleware
    return create_agent(
        model=default_llm,
        tools=[],
        middleware=[DynamicModelMiddleware()],
        checkpointer=checkpointer
    )

workflow = get_workflow()

async def run_agent(thread_id: str, content: str, token_callback, model: str = None):
    async with get_checkpointer() as checkpointer:
        app_with_checkpoint = get_workflow(checkpointer, model_override=model)
        lc_message = HumanMessage(content=content)

        from langchain_core.callbacks import AsyncCallbackHandler

        class StreamingCallbackHandler(AsyncCallbackHandler):
            async def on_llm_new_token(self, token: str, **kwargs):
                import asyncio
                await asyncio.to_thread(token_callback, token)

        handler = StreamingCallbackHandler()

        config = {"configurable": {"thread_id": thread_id}, "callbacks": [handler]}

        final_state = await app_with_checkpoint.ainvoke(
            {"messages": [lc_message]},
            config=config
        )
        
        return final_state["messages"][-1].content
