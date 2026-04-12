import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import List

from app.llm.checkpointer import get_checkpointer
from app.core.database import get_db, get_db_with_schema
from app.auth.models import User
from app.chat.models import Chat
from app.workspace.models import Workspace
from app.chat.schemas import ChatOut, MessageCreate, MessageOut, ChatCreate
from app.core.security import get_current_user, get_current_user_from_query
from app.chat.agent import get_workflow
from app.org.dependencies import get_current_org_membership
from app.tenant.context import get_current_org

router = APIRouter()

TITLE_EVENT_PREFIX = "[TITLE]"

@router.get("/", response_model=List[ChatOut])
async def list_chats(
    request: Request,
    workspace_id: int | None = None,
    skip: int = 0, limit: int = 20,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    org_slug = get_current_org()
    query = select(Chat).where(Chat.user_id == current_user.id)
    if workspace_id is not None:
        query = query.where(Chat.workspace_id == workspace_id)
    result = await db.execute(
        query.order_by(desc(Chat.created_at)).offset(skip).limit(limit)
    )
    return result.scalars().all()

@router.post("/", response_model=ChatOut)
async def create_chat(
    request: Request,
    chat_data: ChatCreate | None = None,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    workspace_id = chat_data.workspace_id if chat_data else None
    model = chat_data.model if chat_data and chat_data.model else "pro"
    if workspace_id is not None:
        # Verify workspace exists in this org
        result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
        if not result.scalars().first():
            raise HTTPException(status_code=404, detail="Workspace not found")

    new_chat = Chat(user_id=current_user.id, workspace_id=workspace_id, title="New Chat", model=model)
    db.add(new_chat)
    await db.commit()
    # Return with ID populated - no refresh needed since commit auto-refreshes
    return new_chat

@router.get("/{chat_id}", response_model=ChatOut)
async def get_chat(
    request: Request,
    chat_id: int,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    result = await db.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id))
    chat = result.scalars().first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat

@router.delete("/{chat_id}")
async def delete_chat(
    request: Request,
    chat_id: int,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    result = await db.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id))
    chat = result.scalars().first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    await db.delete(chat)
    await db.commit()
    return {"status": "success", "message": "Chat deleted"}

@router.get("/{chat_id}/messages", response_model=List[MessageOut])
async def get_messages(
    request: Request,
    chat_id: int,
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    result = await db.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id))
    chat = result.scalars().first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages = []
    async with get_checkpointer() as checkpointer:
        app = get_workflow(checkpointer)
        config = {"configurable": {"thread_id": str(chat_id)}}
        state = await app.aget_state(config)

        if state and state.values:
            langchain_messages = state.values.get("messages", [])
            for msg in langchain_messages:
                role = "user" if msg.type == "human" else "assistant"
                messages.append(MessageOut(
                    id=msg.id or "0",
                    chat_id=chat_id,
                    role=role,
                    content=msg.content,
                    created_at=chat.created_at
                ))

    return messages[skip: skip + limit]

from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis
from app.core.config import settings

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

@router.post("/{chat_id}/messages")
async def send_message(
    request: Request,
    chat_id: int,
    message: MessageCreate,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    result = await db.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id))
    chat = result.scalars().first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Use message model if provided, otherwise use chat model
    model = message.model if message.model else chat.model

    from app.worker.chat_tasks import process_message
    await redis_client.setex(f"chat_processing_{chat_id}", 300, "1")
    org_schema = getattr(request.state, 'org_schema', None)
    process_message.delay(chat_id, message.content, org_schema, model)

    return {"status": "processing", "stream_url": f"/chats/{chat_id}/stream"}

@router.get("/{chat_id}/stream")
async def stream_chat(
    request: Request,
    chat_id: int,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user_from_query),
    membership = Depends(get_current_org_membership),
):
    result = await db.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Chat not found")

    async def event_generator():
        pubsub = redis_client.pubsub()
        channel = f"chat_stream_{chat_id}"
        await pubsub.subscribe(channel)

        is_processing = await redis_client.get(f"chat_processing_{chat_id}")

        async with get_checkpointer() as checkpointer:
            app = get_workflow(checkpointer)
            config = {"configurable": {"thread_id": str(chat_id)}}
            state = await app.aget_state(config)

            if state and state.values:
                messages = state.values.get("messages", [])
                if not is_processing:
                    if messages and messages[-1].type == "ai":
                        yield f"data: {json.dumps(messages[-1].content)}\n\n"
                        yield "data: [DONE]\n\n"
                    elif messages:
                        yield f"data: {json.dumps('[Error: Message generation failed or was interrupted]')}\n\n"
                        yield "data: [DONE]\n\n"
                    await pubsub.unsubscribe(channel)
                    await pubsub.close()
                    return

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    if data == "[DONE]":
                        yield f"data: {data}\n\n"
                        break
                    if data.startswith(TITLE_EVENT_PREFIX):
                        title = data.removeprefix(TITLE_EVENT_PREFIX)
                        yield f"event: title\ndata: {json.dumps(title)}\n\n"
                        continue
                    json_data = json.dumps(data)
                    yield f"data: {json_data}\n\n"
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
