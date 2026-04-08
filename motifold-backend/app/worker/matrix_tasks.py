import json
import logging
import asyncio
import redis
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from app.core.config import settings
from app.matrix.models import MorphologicalAnalysis
from app.matrix.schemas import MorphologicalParameter
from app.matrix.service import generate_morphological_parameters, evaluate_morphological_consistency
from app.worker import celery_app

logger = logging.getLogger(__name__)

sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(bind=engine)

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


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
            "link": f"/matrix?analysis_id={analysis.id}"
        }
        redis_client.publish(channel, json.dumps(notification))
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
            "link": f"/matrix?analysis_id={analysis.id}"
        }
        redis_client.publish(channel, json.dumps(notification))
    finally:
        db.close()
