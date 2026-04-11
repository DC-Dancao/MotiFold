import json
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from typing import Literal

OperationType = Literal["blackboard", "matrix", "research", "chat"]
OperationStatusValue = Literal["pending", "started", "processing", "done", "failed"]

@dataclass
class OperationStatus:
    id: str
    type: OperationType
    status: OperationStatusValue
    message: str
    progress: float = 0.0
    created_at: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def error(id: str, message: str) -> "OperationStatus":
        return OperationStatus(
            id=id,
            type="research",
            status="failed",
            message=message,
            progress=0.0,
            created_at=datetime.now(UTC).isoformat() + "Z",
        )

    @staticmethod
    def not_found(id: str) -> "OperationStatus":
        return OperationStatus(
            id=id,
            type="research",
            status="failed",
            message="Operation not found or expired",
            progress=0.0,
            created_at=datetime.now(UTC).isoformat() + "Z",
        )


async def get_operation_status(task_id: str) -> OperationStatus:
    """
    Look up operation status by task_id.
    Checks Redis for processing flag + research state.
    Falls back to DB for blackboard/matrix records.
    Returns OperationStatus.error() if not found.
    """
    from app.research.stream import get_processing_status, get_research_state
    from app.blackboard.models import BlackboardData
    from app.matrix.models import MorphologicalAnalysis
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select

    # Check research via Redis first
    is_processing = await get_processing_status(task_id)
    if is_processing:
        redis_state = await get_research_state(task_id)
        if redis_state:
            return OperationStatus(
                id=task_id,
                type="research",
                status=_map_research_status(redis_state.get("status", "running")),
                message=redis_state.get("message", "Research in progress"),
                progress=redis_state.get("progress", 0.0),
                created_at=datetime.now(UTC).isoformat() + "Z",
            )

    # Check if it's a blackboard or matrix record (numeric ID)
    try:
        record_id = int(task_id)
        async with AsyncSessionLocal() as session:
            # Check blackboard first
            bb_result = await session.execute(
                select(BlackboardData).where(BlackboardData.id == record_id)
            )
            bb = bb_result.scalars().first()
            if bb:
                return OperationStatus(
                    id=task_id,
                    type="blackboard",
                    status=_map_blackboard_status(bb.status),
                    message=_blackboard_status_message(bb.status),
                    progress=_blackboard_progress(bb.status),
                    created_at=bb.created_at.isoformat() if bb.created_at else "",
                )
            # Check matrix analysis
            ma_result = await session.execute(
                select(MorphologicalAnalysis).where(MorphologicalAnalysis.id == record_id)
            )
            ma = ma_result.scalars().first()
            if ma:
                return OperationStatus(
                    id=task_id,
                    type="matrix",
                    status=_map_matrix_status(ma.status),
                    message=_matrix_status_message(ma.status),
                    progress=_matrix_progress(ma.status),
                    created_at=ma.created_at.isoformat() if ma.created_at else "",
                )
    except ValueError:
        pass

    # Not found
    return OperationStatus.not_found(task_id)


def _map_research_status(status: str) -> OperationStatusValue:
    mapping = {
        "running": "processing",
        "done": "done",
        "error": "failed",
        "start": "started",
    }
    return mapping.get(status, "processing")


def _map_blackboard_status(status: str) -> OperationStatusValue:
    mapping = {
        "pending": "pending",
        "generating": "processing",
        "completed": "done",
        "failed": "failed",
    }
    return mapping.get(status, "pending")


def _blackboard_progress(status: str) -> float:
    mapping = {
        "pending": 0.0,
        "generating": 0.5,
        "completed": 1.0,
        "failed": 0.0,
    }
    return mapping.get(status, 0.0)


def _blackboard_status_message(status: str) -> str:
    mapping = {
        "pending": "Blackboard generation queued",
        "generating": "Blackboard generation in progress",
        "completed": "Blackboard generation complete",
        "failed": "Blackboard generation failed",
    }
    return mapping.get(status, "Unknown status")


def _map_matrix_status(status: str) -> OperationStatusValue:
    mapping = {
        "generating_parameters": "processing",
        "parameters_ready": "done",
        "evaluating_matrix": "processing",
        "matrix_ready": "done",
        "generate_failed": "failed",
        "evaluate_failed": "failed",
    }
    return mapping.get(status, "pending")


def _matrix_progress(status: str) -> float:
    mapping = {
        "generating_parameters": 0.25,
        "parameters_ready": 0.5,
        "evaluating_matrix": 0.75,
        "matrix_ready": 1.0,
        "generate_failed": 0.0,
        "evaluate_failed": 0.0,
    }
    return mapping.get(status, 0.0)


def _matrix_status_message(status: str) -> str:
    mapping = {
        "generating_parameters": "Generating morphological parameters",
        "parameters_ready": "Parameters ready — awaiting evaluation",
        "evaluating_matrix": "Evaluating matrix consistency",
        "matrix_ready": "Matrix evaluation complete",
        "generate_failed": "Parameter generation failed",
        "evaluate_failed": "Consistency evaluation failed",
    }
    return mapping.get(status, "Unknown status")
