import json
import logging
import redis
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, update, text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.async_bridge import run_async_from_sync
from app.matrix.models import MorphologicalAnalysis
from app.matrix.schemas import MorphologicalParameter
from app.matrix.service import generate_morphological_parameters, evaluate_morphological_consistency
from app.matrix.stream import (
    publish_event,
    save_matrix_state,
    get_matrix_state,
    set_processing_flag,
    clear_processing_flag,
)
from app.worker import celery_app

logger = logging.getLogger(__name__)

sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(bind=engine)


@celery_app.task(name="generate_morphological_task")
def generate_morphological_task(analysis_id: int, org_schema: str | None = None):
    async def _run():
        await set_processing_flag(analysis_id)

        # Publish start event to SSE channel
        await publish_event(analysis_id, {
            "type": "status",
            "event": "start",
            "message": "Starting parameter generation...",
        })

        # Fetch analysis for user_id and focus_question
        db_sync = SessionLocal()
        try:
            if org_schema:
                db_sync.execute(text(f'SET search_path TO "{org_schema}", public'))
            analysis = db_sync.query(MorphologicalAnalysis).filter(MorphologicalAnalysis.id == analysis_id).first()
            if not analysis:
                await clear_processing_flag(analysis_id)
                return
            user_id = analysis.user_id
            focus_question = analysis.focus_question
        finally:
            db_sync.close()

        # Save initial state
        await save_matrix_state(analysis_id, {
            "status": "generating_parameters",
            "focus_question": focus_question,
            "message": "Starting parameter generation...",
            "parameters": [],
        })

        # Update DB status
        async with AsyncSessionLocal() as db:
            if org_schema:
                await db.execute(text(f'SET search_path TO "{org_schema}", public'))
            stmt = (
                update(MorphologicalAnalysis)
                .where(MorphologicalAnalysis.id == analysis_id)
                .values(status="generating_parameters")
            )
            await db.execute(stmt)
            await db.commit()

        try:
            # Generate parameters
            response = await generate_morphological_parameters(focus_question)
            parameters_data = [p.model_dump() for p in response.parameters]
            parameters_json = json.dumps(parameters_data)
            final_status = "parameters_ready"
            notification_result = "success"
            message = "参数生成已成功完成。"

            # Update DB with parameters
            async with AsyncSessionLocal() as db:
                if org_schema:
                    await db.execute(text(f'SET search_path TO "{org_schema}", public'))
                stmt = (
                    update(MorphologicalAnalysis)
                    .where(MorphologicalAnalysis.id == analysis_id)
                    .values(
                        parameters_json=parameters_json,
                        status=final_status,
                    )
                )
                await db.execute(stmt)
                await db.commit()

            # Save final state
            await save_matrix_state(analysis_id, {
                "status": final_status,
                "message": message,
                "parameters": parameters_data,
            })

            # Publish [DONE] to SSE channel
            await publish_event(analysis_id, {
                "type": "[DONE]",
                "parameters": parameters_data,
                "status": final_status,
            })

        except Exception as e:
            final_status = "generate_failed"
            notification_result = "error"
            error_msg = str(e)

            if "Too few usable parameters" in error_msg or "Failed to generate valid" in error_msg:
                message = "参数生成执行失败：模型未能生成符合要求的参数配置，请重试或修改聚焦问题。"
            else:
                message = f"参数生成执行失败：{error_msg}"

            logger.error(f"Error in generate_morphological_task: {e}")

            # Update DB with error status
            async with AsyncSessionLocal() as db:
                if org_schema:
                    await db.execute(text(f'SET search_path TO "{org_schema}", public'))
                stmt = (
                    update(MorphologicalAnalysis)
                    .where(MorphologicalAnalysis.id == analysis_id)
                    .values(status=final_status)
                )
                await db.execute(stmt)
                await db.commit()

            # Save error state
            await save_matrix_state(analysis_id, {
                "status": final_status,
                "message": message,
                "error": error_msg,
            })

            # Publish [DONE] with error to SSE channel
            await publish_event(analysis_id, {
                "type": "[DONE]",
                "error": error_msg,
                "status": final_status,
            })

        finally:
            await clear_processing_flag(analysis_id)

        # Publish global notification for cross-tab sync
        redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        channel = f"user_notifications_{user_id}"
        notification = {
            "type": "morphological_analysis",
            "task_type": "generate_parameters",
            "resource_type": "morphological_analysis",
            "resource_id": analysis_id,
            "result": notification_result,
            "status": final_status,
            "title": "参数生成完成" if notification_result == "success" else "参数生成失败",
            "message": message,
            "link": f"/matrix?analysis_id={analysis_id}"
        }
        redis_client.publish(channel, json.dumps(notification))
        redis_client.close()

    run_async_from_sync(_run())


@celery_app.task(name="evaluate_consistency_task")
def evaluate_consistency_task(analysis_id: int, org_schema: str | None = None):
    async def _run():
        await set_processing_flag(analysis_id)

        # Publish start event to SSE channel
        await publish_event(analysis_id, {
            "type": "status",
            "event": "start",
            "message": "Starting consistency evaluation...",
        })

        # Fetch analysis for parameters and user_id
        db_sync = SessionLocal()
        try:
            if org_schema:
                db_sync.execute(text(f'SET search_path TO "{org_schema}", public'))
            analysis = db_sync.query(MorphologicalAnalysis).filter(MorphologicalAnalysis.id == analysis_id).first()
            if not analysis:
                await clear_processing_flag(analysis_id)
                return
            user_id = analysis.user_id
            parameters_json = analysis.parameters_json
        finally:
            db_sync.close()

        # Save initial state
        await save_matrix_state(analysis_id, {
            "status": "evaluating_matrix",
            "focus_question": analysis.focus_question,
            "message": "Starting consistency evaluation...",
            "matrix": {},
        })

        # Update DB status
        async with AsyncSessionLocal() as db:
            if org_schema:
                await db.execute(text(f'SET search_path TO "{org_schema}", public'))
            stmt = (
                update(MorphologicalAnalysis)
                .where(MorphologicalAnalysis.id == analysis_id)
                .values(status="evaluating_matrix")
            )
            await db.execute(stmt)
            await db.commit()

        try:
            # Evaluate consistency
            parameters = [MorphologicalParameter(**p) for p in json.loads(parameters_json)]
            if not parameters:
                raise ValueError("No parameters found")

            response = await evaluate_morphological_consistency(parameters)
            matrix_data = response.get("matrix", {})
            matrix_json = json.dumps(matrix_data)
            final_status = "matrix_ready"
            notification_result = "success"
            message = "一致性评估已成功完成。"

            # Update DB with matrix
            async with AsyncSessionLocal() as db:
                if org_schema:
                    await db.execute(text(f'SET search_path TO "{org_schema}", public'))
                stmt = (
                    update(MorphologicalAnalysis)
                    .where(MorphologicalAnalysis.id == analysis_id)
                    .values(
                        matrix_json=matrix_json,
                        status=final_status,
                    )
                )
                await db.execute(stmt)
                await db.commit()

            # Save final state
            await save_matrix_state(analysis_id, {
                "status": final_status,
                "message": message,
                "matrix": matrix_data,
            })

            # Publish [DONE] to SSE channel
            await publish_event(analysis_id, {
                "type": "[DONE]",
                "matrix": matrix_data,
                "status": final_status,
            })

        except Exception as e:
            final_status = "evaluate_failed"
            notification_result = "error"
            error_msg = str(e)

            if "Failed to evaluate consistency after" in error_msg:
                message = "一致性评估执行失败：模型无法生成符合格式的结果，请尝试重新生成或简化问题。"
            else:
                message = f"一致性评估执行失败：{error_msg}"

            logger.error(f"Error in evaluate_consistency_task: {e}")

            # Update DB with error status
            async with AsyncSessionLocal() as db:
                if org_schema:
                    await db.execute(text(f'SET search_path TO "{org_schema}", public'))
                stmt = (
                    update(MorphologicalAnalysis)
                    .where(MorphologicalAnalysis.id == analysis_id)
                    .values(status=final_status)
                )
                await db.execute(stmt)
                await db.commit()

            # Save error state
            await save_matrix_state(analysis_id, {
                "status": final_status,
                "message": message,
                "error": error_msg,
            })

            # Publish [DONE] with error to SSE channel
            await publish_event(analysis_id, {
                "type": "[DONE]",
                "error": error_msg,
                "status": final_status,
            })

        finally:
            await clear_processing_flag(analysis_id)

        # Publish global notification for cross-tab sync
        redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        channel = f"user_notifications_{user_id}"
        notification = {
            "type": "morphological_analysis",
            "task_type": "evaluate_consistency",
            "resource_type": "morphological_analysis",
            "resource_id": analysis_id,
            "result": notification_result,
            "status": final_status,
            "title": "一致性评估完成" if notification_result == "success" else "一致性评估失败",
            "message": message,
            "link": f"/matrix?analysis_id={analysis_id}"
        }
        redis_client.publish(channel, json.dumps(notification))
        redis_client.close()

    run_async_from_sync(_run())
