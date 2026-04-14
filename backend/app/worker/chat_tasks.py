import json
import logging
import asyncio
import redis
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.async_bridge import run_async_from_sync
from app.chat.models import Chat
from app.chat.agent import run_agent
from app.llm.factory import get_llm
from app.worker import celery_app

logger = logging.getLogger(__name__)

sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(bind=engine)

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
TITLE_EVENT_PREFIX = "[TITLE]"


# Module-level async engine singleton for memory operations
_memory_async_engine = None
_memory_async_session_maker = None


def _get_memory_async_engine():
    """Get or create the async engine singleton for memory operations."""
    global _memory_async_engine, _memory_async_session_maker
    if _memory_async_engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        async_db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        _memory_async_engine = create_async_engine(async_db_url, pool_pre_ping=True)
        _memory_async_session_maker = async_sessionmaker(
            _memory_async_engine, expire_on_commit=False
        )
    return _memory_async_engine, _memory_async_session_maker


def enrich_content_with_memory(session, workspace_id: int, content: str) -> str:
    """
    Enrich user content with relevant memories from the workspace.

    Args:
        session: Database session
        workspace_id: Workspace ID for memory lookup
        content: Original user message

    Returns:
        Enriched content with memory context prepended
    """
    try:
        from app.memory.service import MemoryService

        _, async_session_maker = _get_memory_async_engine()

        async def _get_memories():
            async with async_session_maker() as async_session:
                memory_service = MemoryService(async_session)
                memories = await memory_service.recall(
                    workspace_id=workspace_id,
                    query=content,
                    limit=3,
                    max_tokens=1000,
                )
                return memories

        # Run async memory lookup
        memories = run_async_from_sync(_get_memories())

        if memories:
            memory_context = "\n\n[相关记忆]\n" + "\n".join(
                f"- {m.content}" for m in memories
            )
            return content + memory_context

    except Exception as e:
        logger.warning(f"Failed to enrich content with memory: {e}")

    return content


def store_conversation_in_memory(session, workspace_id: int, user_message: str, assistant_response: str):
    """
    Store a conversation exchange in workspace memory.

    Args:
        session: Database session
        workspace_id: Workspace ID
        user_message: User's message
        assistant_response: Assistant's response
    """
    if not workspace_id:
        return

    try:
        from app.memory.service import MemoryService

        _, async_session_maker = _get_memory_async_engine()

        async def _store():
            async with async_session_maker() as async_session:
                memory_service = MemoryService(async_session)
                # Store user message
                await memory_service.retain(
                    workspace_id=workspace_id,
                    content=f"用户: {user_message}",
                    memory_type="fact",
                )
                # Store assistant response
                await memory_service.retain(
                    workspace_id=workspace_id,
                    content=f"助手: {assistant_response}",
                    memory_type="fact",
                )

        run_async_from_sync(_store())
        logger.debug(f"Stored conversation in memory for workspace {workspace_id}")

    except Exception as e:
        logger.warning(f"Failed to store conversation in memory: {e}")


def generate_chat_title_text(first_message: str) -> str:
    from langchain_core.messages import SystemMessage, HumanMessage

    llm = get_llm(streaming=False)
    response = llm.invoke([
        SystemMessage(content="Generate a short title (max 5 words) for a chat that starts with the following message. Return ONLY the title, no quotes."),
        HumanMessage(content=first_message)
    ])
    return response.content.strip()


def update_chat_title(chat_id: int, first_message: str, db=None, publish: bool = False) -> str | None:
    owns_session = db is None
    session = db or SessionLocal()

    try:
        chat = session.query(Chat).filter(Chat.id == chat_id).first()
        if not chat or chat.title != "New Chat":
            return None

        title = generate_chat_title_text(first_message)
        if not title:
            return None

        chat.title = title
        if owns_session:
            session.commit()

        if publish:
            redis_client.publish(f"chat_stream_{chat_id}", f"{TITLE_EVENT_PREFIX}{title}")

        return title
    except Exception:
        if owns_session:
            session.rollback()
        return None
    finally:
        if owns_session:
            session.close()

@celery_app.task(name="process_message")
def process_message(chat_id: int, content: str, org_schema: str | None = None, model: str = "pro", solutions_mode: bool = False):
    db = SessionLocal()
    # Set search_path to org schema if provided
    if org_schema:
        db.execute(text(f'SET search_path TO "{org_schema}", public'))
    try:
        # Load history
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            return

        # Get workspace_id for memory lookup
        workspace_id = chat.workspace_id

        # Enrich content with relevant memories (skip for solutions mode - no memory enrichment needed)
        enriched_content = content
        if workspace_id and not solutions_mode:
            enriched_content = enrich_content_with_memory(db, workspace_id, content)

        # Publish tokens to redis
        channel = f"chat_stream_{chat_id}"

        # Sync function to publish to redis
        def token_callback(token):
            redis_client.publish(channel, token)

        try:
            # Use "auto" if model is "auto" or not set, otherwise use specific model
            model_override = None if (model == "auto" or model is None) else model
            response = run_async_from_sync(run_agent(
                str(chat_id), enriched_content, token_callback,
                model=model_override, solutions_mode=solutions_mode
            ))

            # Store conversation in memory after successful response (skip for solutions mode)
            if workspace_id and response and not solutions_mode:
                store_conversation_in_memory(db, workspace_id, content, response)

            # Check if auto-title needed (skip for solutions mode)
            if chat.title == "New Chat" and not solutions_mode:
                generate_title.delay(chat_id, content)

            db.commit()
        except Exception as e:
            redis_client.publish(channel, f"Error: {str(e)}")
        finally:
            redis_client.delete(f"chat_processing_{chat_id}")
            redis_client.publish(channel, "[DONE]")

    finally:
        db.close()

@celery_app.task(name="generate_title")
def generate_title(chat_id: int, first_message: str):
    update_chat_title(chat_id, first_message, publish=True)
