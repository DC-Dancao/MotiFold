import json
import logging
import asyncio
import redis
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.blackboard.models import BlackboardData
from app.blackboard.agent import run_blackboard_agent
from app.worker import celery_app

logger = logging.getLogger(__name__)

sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(bind=engine)

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


@celery_app.task(name="generate_blackboard_task")
def generate_blackboard_task(blackboard_id: int, topic: str, org_schema: str | None = None):
    """
    Asynchronous task to generate a blackboard explanation using the LangGraph agent.
    """
    logger.info(f"Starting blackboard generation for blackboard {blackboard_id}")
    db: Session = SessionLocal()
    try:
        # Set search_path to org schema if provided
        if org_schema:
            db.execute(text(f'SET search_path TO "{org_schema}", public'))

        # 1. Update status to generating
        bb_record = db.query(BlackboardData).filter(BlackboardData.id == blackboard_id).first()
        if not bb_record:
            logger.error(f"BlackboardData {blackboard_id} not found.")
            return

        bb_record.status = "generating"
        user_id = bb_record.user_id
        db.commit()

        # 2. Run the blackboard LangGraph agent
        steps_data = asyncio.run(run_blackboard_agent(topic))

        # 3. Save result and update status
        bb_record.content_json = json.dumps(steps_data, ensure_ascii=False)
        bb_record.status = "completed"
        db.commit()

        # 4. Notify frontend
        message = json.dumps({
            "type": "blackboard_updated",
            "blackboard_id": blackboard_id,
            "status": "completed"
        })
        logger.info(f"Publishing blackboard_updated event for blackboard {blackboard_id}")
        redis_client.publish(f"user_notifications_{user_id}", message)

    except Exception as e:
        logger.error(f"Error in generate_blackboard_task for blackboard {blackboard_id}: {str(e)}", exc_info=True)
        db.rollback()
        
        bb_record = db.query(BlackboardData).filter(BlackboardData.id == blackboard_id).first()
        if bb_record:
            user_id = bb_record.user_id
            bb_record.status = "failed"
            db.commit()
            
            error_message = json.dumps({
                "type": "blackboard_updated",
                "blackboard_id": blackboard_id,
                "status": "failed"
            })
            redis_client.publish(f"user_notifications_{user_id}", error_message)
    finally:
        db.close()
