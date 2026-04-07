import json
import logging
from celery import Celery
import asyncio
import redis
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)
from sqlalchemy import create_engine
from app.config import settings
from app.models import Chat, MorphologicalAnalysis
from app.langgraph_agent import run_agent
from app.blackboard_agent import run_blackboard_agent
from app.matrix_service import generate_morphological_parameters, evaluate_morphological_consistency
from app.routers.matrix_router import MorphologicalParameter

celery_app = Celery(__name__)
celery_app.conf.broker_url = settings.REDIS_URL
celery_app.conf.result_backend = settings.REDIS_URL

sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(bind=engine)

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
TITLE_EVENT_PREFIX = "[TITLE]"


def generate_chat_title_text(first_message: str) -> str:
    from app.llm import get_llm
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

@celery_app.task(name="generate_morphological_task")
def generate_morphological_task(analysis_id: int):
    db = SessionLocal()
    try:
        analysis = db.query(MorphologicalAnalysis).filter(MorphologicalAnalysis.id == analysis_id).first()
        if not analysis:
            return
            
        try:
            response = asyncio.run(generate_morphological_parameters(analysis.focus_question))
            parameters_json = json.dumps([p.model_dump() for p in response.parameters])
            analysis.parameters_json = parameters_json
            analysis.status = "parameters_ready"
            notification_result = "success"
            message = "参数生成已成功完成。"
        except Exception as e:
            analysis.status = "generate_failed"
            notification_result = "error"
            
            error_msg = str(e)
            if "Too few usable parameters" in error_msg or "Failed to generate valid" in error_msg:
                message = "参数生成执行失败：模型未能生成符合要求的参数配置，请重试或修改聚焦问题。"
            else:
                message = f"参数生成执行失败：{error_msg}"
                
            print(f"Error in generate_morphological_task: {e}")
            
        db.commit()
        
        # Notify the user via SSE
        channel = f"user_notifications_{analysis.user_id}"
        notification = {
            "type": "morphological_analysis",
            "task_type": "generate_parameters",
            "resource_type": "morphological_analysis",
            "resource_id": analysis.id,
            "result": notification_result,
            "status": analysis.status,
            "title": "参数生成任务",
            "message": message,
            "link": f"/?view=matrix&analysis_id={analysis.id}"
        }
        redis_client.publish(channel, json.dumps(notification))
    finally:
        db.close()


@celery_app.task(name="generate_blackboard_task")
def generate_blackboard_task(blackboard_id: int, topic: str):
    """
    Asynchronous task to generate a blackboard explanation using the LangGraph agent.
    """
    logger.info(f"Starting blackboard generation for blackboard {blackboard_id}")
    db: Session = SessionLocal()
    try:
        from app.models import BlackboardData
        
        # 1. Update status to generating
        bb_record = db.query(BlackboardData).filter(BlackboardData.id == blackboard_id).first()
        if not bb_record:
            logger.error(f"BlackboardData {blackboard_id} not found.")
            return

        bb_record.status = "generating"
        db.commit()

        # 2. Run the blackboard LangGraph agent
        loop = asyncio.get_event_loop()
        steps_data = loop.run_until_complete(run_blackboard_agent(topic))

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
        redis_client.publish("notifications", message)

    except Exception as e:
        logger.error(f"Error in generate_blackboard_task for blackboard {blackboard_id}: {str(e)}", exc_info=True)
        db.rollback()
        
        from app.models import BlackboardData
        bb_record = db.query(BlackboardData).filter(BlackboardData.id == blackboard_id).first()
        if bb_record:
            bb_record.status = "failed"
            db.commit()
            
            error_message = json.dumps({
                "type": "blackboard_updated",
                "blackboard_id": blackboard_id,
                "status": "failed"
            })
            redis_client.publish("notifications", error_message)
    finally:
        db.close()


@celery_app.task(name="evaluate_consistency_task")
def evaluate_consistency_task(analysis_id: int):
    db = SessionLocal()
    try:
        analysis = db.query(MorphologicalAnalysis).filter(MorphologicalAnalysis.id == analysis_id).first()
        if not analysis:
            return
            
        try:
            parameters = [MorphologicalParameter(**p) for p in json.loads(analysis.parameters_json)]
            if not parameters:
                raise ValueError("No parameters found")
                
            response = asyncio.run(evaluate_morphological_consistency(parameters))
            analysis.matrix_json = json.dumps(response.get("matrix", {}))
            analysis.status = "matrix_ready"
            notification_result = "success"
            message = "一致性评估已成功完成。"
        except Exception as e:
            analysis.status = "evaluate_failed"
            notification_result = "error"
            
            # Extract detailed error if possible
            error_msg = str(e)
            if "Failed to evaluate consistency after" in error_msg:
                message = "一致性评估执行失败：模型无法生成符合格式的结果，请尝试重新生成或简化问题。"
            else:
                message = f"一致性评估执行失败：{error_msg}"
                
            print(f"Error in evaluate_consistency_task: {e}")
            
        db.commit()
        
        # Notify the user via SSE
        channel = f"user_notifications_{analysis.user_id}"
        notification = {
            "type": "morphological_analysis",
            "task_type": "evaluate_consistency",
            "resource_type": "morphological_analysis",
            "resource_id": analysis.id,
            "result": notification_result,
            "status": analysis.status,
            "title": "一致性评估任务",
            "message": message,
            "link": f"/?view=matrix&analysis_id={analysis.id}"
        }
        redis_client.publish(channel, json.dumps(notification))
    finally:
        db.close()
