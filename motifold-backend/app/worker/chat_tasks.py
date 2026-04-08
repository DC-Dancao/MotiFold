import json
import logging
import asyncio
import redis
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from app.core.config import settings
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
def process_message(chat_id: int, content: str):
    db = SessionLocal()
    try:
        # Load history
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            return

        # Publish tokens to redis
        channel = f"chat_stream_{chat_id}"

        # Sync function to publish to redis
        def token_callback(token):
            redis_client.publish(channel, token)

        try:
            asyncio.run(run_agent(str(chat_id), content, token_callback))

            # Check if auto-title needed
            if chat.title == "New Chat":
                update_chat_title(chat_id, content, db=db, publish=True)

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
