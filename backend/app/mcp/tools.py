import json
import logging
from dataclasses import dataclass
from typing import Callable

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import AsyncSessionLocal
from app.workspace.models import Workspace
from app.chat.models import Chat, Message
from app.matrix.models import MorphologicalAnalysis
from app.blackboard.models import BlackboardData
from app.research.models import ResearchReport
from app.mcp.operations import OperationStatus, get_operation_status

logger = logging.getLogger(__name__)

ALL_TOOLS = frozenset({
    # Workspace
    "workspace_list", "workspace_get", "workspace_create", "workspace_delete",
    # Chat
    "chat_list", "chat_get", "chat_create", "chat_send_message", "chat_get_history",
    # Matrix
    "matrix_list_analyses", "matrix_get_analysis", "matrix_start_analysis",
    "matrix_evaluate_consistency", "matrix_save_analysis", "matrix_delete_analysis",
    # Blackboard
    "blackboard_list", "blackboard_get", "blackboard_generate", "blackboard_delete",
    # Research
    "research_list_reports", "research_get_report", "research_start",
    "research_get_result", "research_get_state", "research_delete_report",
    # Memory
    "memory_recall", "memory_retain", "memory_get_stats", "memory_get_entity_memories",
    # Operations
    "operation_list", "operation_get_status",
})


@dataclass
class MCPToolsConfig:
    user_id_resolver: Callable[[], int | None]
    tools: set[str] | None = None  # None means all tools


def register_mcp_tools(mcp: FastMCP, config: MCPToolsConfig) -> None:
    """Register all configured MCP tools on the FastMCP server."""
    tools_to_register = config.tools or ALL_TOOLS

    if "workspace_list" in tools_to_register:
        _register_workspace_list(mcp, config)
    if "workspace_get" in tools_to_register:
        _register_workspace_get(mcp, config)
    if "workspace_create" in tools_to_register:
        _register_workspace_create(mcp, config)
    if "workspace_delete" in tools_to_register:
        _register_workspace_delete(mcp, config)

    if "chat_list" in tools_to_register:
        _register_chat_list(mcp, config)
    if "chat_get" in tools_to_register:
        _register_chat_get(mcp, config)
    if "chat_create" in tools_to_register:
        _register_chat_create(mcp, config)
    if "chat_send_message" in tools_to_register:
        _register_chat_send_message(mcp, config)
    if "chat_get_history" in tools_to_register:
        _register_chat_get_history(mcp, config)

    if "matrix_list_analyses" in tools_to_register:
        _register_matrix_list_analyses(mcp, config)
    if "matrix_get_analysis" in tools_to_register:
        _register_matrix_get_analysis(mcp, config)
    if "matrix_start_analysis" in tools_to_register:
        _register_matrix_start_analysis(mcp, config)
    if "matrix_evaluate_consistency" in tools_to_register:
        _register_matrix_evaluate_consistency(mcp, config)
    if "matrix_save_analysis" in tools_to_register:
        _register_matrix_save_analysis(mcp, config)
    if "matrix_delete_analysis" in tools_to_register:
        _register_matrix_delete_analysis(mcp, config)

    if "blackboard_list" in tools_to_register:
        _register_blackboard_list(mcp, config)
    if "blackboard_get" in tools_to_register:
        _register_blackboard_get(mcp, config)
    if "blackboard_generate" in tools_to_register:
        _register_blackboard_generate(mcp, config)
    if "blackboard_delete" in tools_to_register:
        _register_blackboard_delete(mcp, config)

    if "research_list_reports" in tools_to_register:
        _register_research_list_reports(mcp, config)
    if "research_get_report" in tools_to_register:
        _register_research_get_report(mcp, config)
    if "research_start" in tools_to_register:
        _register_research_start(mcp, config)
    if "research_get_result" in tools_to_register:
        _register_research_get_result(mcp, config)
    if "research_get_state" in tools_to_register:
        _register_research_get_state(mcp, config)
    if "research_delete_report" in tools_to_register:
        _register_research_delete_report(mcp, config)

    if "memory_recall" in tools_to_register:
        _register_memory_recall(mcp, config)
    if "memory_retain" in tools_to_register:
        _register_memory_retain(mcp, config)
    if "memory_get_stats" in tools_to_register:
        _register_memory_get_stats(mcp, config)
    if "memory_get_entity_memories" in tools_to_register:
        _register_memory_get_entity_memories(mcp, config)

    if "operation_list" in tools_to_register:
        _register_operation_list(mcp, config)
    if "operation_get_status" in tools_to_register:
        _register_operation_get_status(mcp, config)


# =============================================================================
# Workspace Tools
# =============================================================================

def _register_workspace_list(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def workspace_list() -> str:
        """List all workspaces for the authenticated user."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized: No user_id configured").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Workspace).where(Workspace.user_id == user_id))
                workspaces = result.scalars().all()
                return json.dumps({
                    "workspaces": [
                        {"id": w.id, "name": w.name, "created_at": w.created_at.isoformat()}
                        for w in workspaces
                    ]
                })
        except Exception as e:
            logger.error(f"Error listing workspaces: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_workspace_get(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def workspace_get(workspace_id: int) -> str:
        """Get a workspace by ID."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(workspace_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
                )
                workspace = result.scalars().first()
                if not workspace:
                    return OperationStatus.error(str(workspace_id), f"Workspace {workspace_id} not found").to_json()
                return json.dumps({
                    "id": workspace.id,
                    "name": workspace.name,
                    "created_at": workspace.created_at.isoformat(),
                })
        except Exception as e:
            logger.error(f"Error getting workspace: {e}", exc_info=True)
            return OperationStatus.error(str(workspace_id), str(e)).to_json()


def _register_workspace_create(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def workspace_create(name: str) -> str:
        """Create a new workspace."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                workspace = Workspace(user_id=user_id, name=name)
                session.add(workspace)
                await session.commit()
                await session.refresh(workspace)
                return json.dumps({
                    "id": workspace.id,
                    "name": workspace.name,
                    "created_at": workspace.created_at.isoformat(),
                })
        except Exception as e:
            logger.error(f"Error creating workspace: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_workspace_delete(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def workspace_delete(workspace_id: int) -> str:
        """Delete a workspace."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(workspace_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
                )
                workspace = result.scalars().first()
                if not workspace:
                    return OperationStatus.error(str(workspace_id), f"Workspace {workspace_id} not found").to_json()
                await session.delete(workspace)
                await session.commit()
                return json.dumps({"status": "success", "message": f"Workspace {workspace_id} deleted"})
        except Exception as e:
            logger.error(f"Error deleting workspace: {e}", exc_info=True)
            return OperationStatus.error(str(workspace_id), str(e)).to_json()


# =============================================================================
# Chat Tools
# =============================================================================

def _register_chat_list(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def chat_list(workspace_id: int | None = None) -> str:
        """List chats for the authenticated user, optionally filtered by workspace."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Chat).where(Chat.user_id == user_id)
                if workspace_id is not None:
                    stmt = stmt.where(Chat.workspace_id == workspace_id)
                result = await session.execute(stmt.order_by(Chat.created_at.desc()))
                chats = result.scalars().all()
                return json.dumps({
                    "chats": [
                        {"id": c.id, "title": c.title, "workspace_id": c.workspace_id, "created_at": c.created_at.isoformat()}
                        for c in chats
                    ]
                })
        except Exception as e:
            logger.error(f"Error listing chats: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_chat_get(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def chat_get(chat_id: int) -> str:
        """Get a chat by ID."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(chat_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
                )
                chat = result.scalars().first()
                if not chat:
                    return OperationStatus.error(str(chat_id), f"Chat {chat_id} not found").to_json()
                return json.dumps({
                    "id": chat.id,
                    "title": chat.title,
                    "workspace_id": chat.workspace_id,
                    "created_at": chat.created_at.isoformat(),
                })
        except Exception as e:
            logger.error(f"Error getting chat: {e}", exc_info=True)
            return OperationStatus.error(str(chat_id), str(e)).to_json()


def _register_chat_create(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def chat_create(workspace_id: int | None = None) -> str:
        """Create a new chat, optionally in a workspace."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                if workspace_id is not None:
                    ws_result = await session.execute(
                        select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
                    )
                    if not ws_result.scalars().first():
                        return OperationStatus.error("0", f"Workspace {workspace_id} not found").to_json()

                chat = Chat(user_id=user_id, workspace_id=workspace_id, title="New Chat")
                session.add(chat)
                await session.commit()
                await session.refresh(chat)
                return json.dumps({
                    "id": chat.id,
                    "title": chat.title,
                    "workspace_id": chat.workspace_id,
                    "created_at": chat.created_at.isoformat(),
                })
        except Exception as e:
            logger.error(f"Error creating chat: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_chat_send_message(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def chat_send_message(chat_id: int, content: str) -> str:
        """Send a message to a chat (async via Celery)."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(chat_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
                )
                chat = result.scalars().first()
                if not chat:
                    return OperationStatus.error(str(chat_id), f"Chat {chat_id} not found").to_json()

            from app.worker.chat_tasks import process_message
            import redis.asyncio as aioredis
            from app.core.config import settings
            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            try:
                await redis_client.setex(f"chat_processing_{chat_id}", 300, "1")
            finally:
                await redis_client.aclose()
            process_message.delay(chat_id, content)

            return OperationStatus(
                id=str(chat_id),
                type="chat",
                status="started",
                message="Message sent. Poll with operation_get_status to track processing.",
                progress=0.0,
            ).to_json()
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return OperationStatus.error(str(chat_id), str(e)).to_json()


def _register_chat_get_history(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def chat_get_history(chat_id: int, limit: int = 50) -> str:
        """Get message history for a chat."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(chat_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
                )
                chat = result.scalars().first()
                if not chat:
                    return OperationStatus.error(str(chat_id), f"Chat {chat_id} not found").to_json()

                msg_result = await session.execute(
                    select(Message)
                    .where(Message.chat_id == chat_id)
                    .order_by(Message.created_at.desc())
                    .limit(limit)
                )
                messages = msg_result.scalars().all()
                messages.reverse()

                return json.dumps({
                    "messages": [
                        {
                            "id": m.id,
                            "role": m.role,
                            "content": m.content,
                            "created_at": m.created_at.isoformat(),
                        }
                        for m in messages
                    ]
                })
        except Exception as e:
            logger.error(f"Error getting chat history: {e}", exc_info=True)
            return OperationStatus.error(str(chat_id), str(e)).to_json()


# =============================================================================
# Matrix Tools
# =============================================================================

def _register_matrix_list_analyses(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def matrix_list_analyses(workspace_id: int | None = None) -> str:
        """List all morphological analyses for the authenticated user."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                stmt = select(MorphologicalAnalysis).where(MorphologicalAnalysis.user_id == user_id)
                if workspace_id is not None:
                    stmt = stmt.where(MorphologicalAnalysis.workspace_id == workspace_id)
                result = await session.execute(stmt.order_by(MorphologicalAnalysis.updated_at.desc()))
                analyses = result.scalars().all()
                return json.dumps({
                    "analyses": [
                        {
                            "id": a.id,
                            "focus_question": a.focus_question,
                            "status": a.status,
                            "created_at": a.created_at.isoformat(),
                        }
                        for a in analyses
                    ]
                })
        except Exception as e:
            logger.error(f"Error listing analyses: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_matrix_get_analysis(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def matrix_get_analysis(analysis_id: int) -> str:
        """Get a morphological analysis by ID."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(analysis_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(MorphologicalAnalysis).where(
                        MorphologicalAnalysis.id == analysis_id,
                        MorphologicalAnalysis.user_id == user_id,
                    )
                )
                analysis = result.scalars().first()
                if not analysis:
                    return OperationStatus.error(str(analysis_id), f"Analysis {analysis_id} not found").to_json()
                return json.dumps({
                    "id": analysis.id,
                    "focus_question": analysis.focus_question,
                    "parameters": json.loads(analysis.parameters_json),
                    "matrix": json.loads(analysis.matrix_json),
                    "status": analysis.status,
                    "created_at": analysis.created_at.isoformat(),
                    "updated_at": analysis.updated_at.isoformat(),
                })
        except Exception as e:
            logger.error(f"Error getting analysis: {e}", exc_info=True)
            return OperationStatus.error(str(analysis_id), str(e)).to_json()


def _register_matrix_start_analysis(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def matrix_start_analysis(focus_question: str, workspace_id: int | None = None) -> str:
        """Start a new morphological analysis (async via Celery)."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                analysis = MorphologicalAnalysis(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    focus_question=focus_question,
                    parameters_json="[]",
                    matrix_json="{}",
                    status="generating_parameters",
                )
                session.add(analysis)
                await session.commit()
                await session.refresh(analysis)

                from app.worker.matrix_tasks import generate_morphological_task
                generate_morphological_task.delay(analysis.id)

                status = OperationStatus(
                    id=str(analysis.id),
                    type="matrix",
                    status="started",
                    message="Morphological analysis started. Poll with operation_get_status.",
                    progress=0.0,
                    created_at=analysis.created_at.isoformat(),
                )
                return status.to_json()
        except Exception as e:
            logger.error(f"Error starting analysis: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_matrix_evaluate_consistency(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def matrix_evaluate_consistency(analysis_id: int) -> str:
        """Start consistency evaluation for a morphological analysis (async)."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(analysis_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(MorphologicalAnalysis).where(
                        MorphologicalAnalysis.id == analysis_id,
                        MorphologicalAnalysis.user_id == user_id,
                    )
                )
                analysis = result.scalars().first()
                if not analysis:
                    return OperationStatus.error(str(analysis_id), f"Analysis {analysis_id} not found").to_json()
                if analysis.status not in ("parameters_ready", "matrix_ready", "evaluate_failed"):
                    return OperationStatus.error(
                        str(analysis_id),
                        f"Analysis not ready for evaluation (status: {analysis.status})"
                    ).to_json()

                analysis.status = "evaluating_matrix"
                await session.commit()

                from app.worker.matrix_tasks import evaluate_consistency_task
                evaluate_consistency_task.delay(analysis_id)

                status = OperationStatus(
                    id=str(analysis_id),
                    type="matrix",
                    status="started",
                    message="Matrix consistency evaluation started. Poll with operation_get_status.",
                    progress=0.0,
                )
                return status.to_json()
        except Exception as e:
            logger.error(f"Error starting evaluation: {e}", exc_info=True)
            return OperationStatus.error(str(analysis_id), str(e)).to_json()


def _register_matrix_save_analysis(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def matrix_save_analysis(
        focus_question: str,
        parameters: list,
        matrix: dict,
        analysis_id: int | None = None,
    ) -> str:
        """Save or update a morphological analysis."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                parameters_json = json.dumps(parameters)
                matrix_json = json.dumps(matrix)

                if analysis_id is not None:
                    result = await session.execute(
                        select(MorphologicalAnalysis).where(
                            MorphologicalAnalysis.id == analysis_id,
                            MorphologicalAnalysis.user_id == user_id,
                        )
                    )
                    analysis = result.scalars().first()
                    if not analysis:
                        return OperationStatus.error(str(analysis_id), f"Analysis {analysis_id} not found").to_json()
                    analysis.focus_question = focus_question
                    analysis.parameters_json = parameters_json
                    analysis.matrix_json = matrix_json
                else:
                    analysis = MorphologicalAnalysis(
                        user_id=user_id,
                        focus_question=focus_question,
                        parameters_json=parameters_json,
                        matrix_json=matrix_json,
                    )
                    session.add(analysis)

                await session.commit()
                await session.refresh(analysis)
                return json.dumps({
                    "id": analysis.id,
                    "focus_question": analysis.focus_question,
                    "status": analysis.status,
                })
        except Exception as e:
            logger.error(f"Error saving analysis: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_matrix_delete_analysis(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def matrix_delete_analysis(analysis_id: int) -> str:
        """Delete a morphological analysis."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(analysis_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(MorphologicalAnalysis).where(
                        MorphologicalAnalysis.id == analysis_id,
                        MorphologicalAnalysis.user_id == user_id,
                    )
                )
                analysis = result.scalars().first()
                if not analysis:
                    return OperationStatus.error(str(analysis_id), f"Analysis {analysis_id} not found").to_json()
                await session.delete(analysis)
                await session.commit()
                return json.dumps({"status": "success", "message": f"Analysis {analysis_id} deleted"})
        except Exception as e:
            logger.error(f"Error deleting analysis: {e}", exc_info=True)
            return OperationStatus.error(str(analysis_id), str(e)).to_json()


# =============================================================================
# Blackboard Tools
# =============================================================================

def _register_blackboard_list(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def blackboard_list(workspace_id: int | None = None) -> str:
        """List blackboard history for the authenticated user."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                stmt = select(BlackboardData).where(BlackboardData.user_id == user_id)
                if workspace_id is not None:
                    stmt = stmt.where(BlackboardData.workspace_id == workspace_id)
                result = await session.execute(stmt.order_by(BlackboardData.created_at.desc()))
                records = result.scalars().all()
                return json.dumps({
                    "blackboards": [
                        {
                            "id": r.id,
                            "topic": r.topic,
                            "status": r.status,
                            "created_at": r.created_at.isoformat(),
                        }
                        for r in records
                    ]
                })
        except Exception as e:
            logger.error(f"Error listing blackboards: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_blackboard_get(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def blackboard_get(blackboard_id: int) -> str:
        """Get a blackboard by ID."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(blackboard_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(BlackboardData).where(
                        BlackboardData.id == blackboard_id,
                        BlackboardData.user_id == user_id,
                    )
                )
                bb = result.scalars().first()
                if not bb:
                    return OperationStatus.error(str(blackboard_id), f"Blackboard {blackboard_id} not found").to_json()
                return json.dumps({
                    "id": bb.id,
                    "topic": bb.topic,
                    "status": bb.status,
                    "content": json.loads(bb.content_json),
                    "created_at": bb.created_at.isoformat(),
                })
        except Exception as e:
            logger.error(f"Error getting blackboard: {e}", exc_info=True)
            return OperationStatus.error(str(blackboard_id), str(e)).to_json()


def _register_blackboard_generate(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def blackboard_generate(topic: str, workspace_id: int | None = None) -> str:
        """Generate a new blackboard for a topic (async via Celery)."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                bb = BlackboardData(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    topic=topic,
                    status="pending",
                    content_json="[]",
                )
                session.add(bb)
                await session.commit()
                await session.refresh(bb)

                from app.worker.blackboard_tasks import generate_blackboard_task
                generate_blackboard_task.delay(bb.id, topic)

                status = OperationStatus(
                    id=str(bb.id),
                    type="blackboard",
                    status="started",
                    message="Blackboard generation started. Poll with operation_get_status.",
                    progress=0.0,
                    created_at=bb.created_at.isoformat(),
                )
                return status.to_json()
        except Exception as e:
            logger.error(f"Error generating blackboard: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_blackboard_delete(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def blackboard_delete(blackboard_id: int) -> str:
        """Delete a blackboard."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(blackboard_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(BlackboardData).where(
                        BlackboardData.id == blackboard_id,
                        BlackboardData.user_id == user_id,
                    )
                )
                bb = result.scalars().first()
                if not bb:
                    return OperationStatus.error(str(blackboard_id), f"Blackboard {blackboard_id} not found").to_json()
                await session.delete(bb)
                await session.commit()
                return json.dumps({"status": "success", "message": f"Blackboard {blackboard_id} deleted"})
        except Exception as e:
            logger.error(f"Error deleting blackboard: {e}", exc_info=True)
            return OperationStatus.error(str(blackboard_id), str(e)).to_json()


# =============================================================================
# Research Tools
# =============================================================================

def _register_research_list_reports(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def research_list_reports() -> str:
        """List all research reports for the authenticated user."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ResearchReport)
                    .where(ResearchReport.user_id == user_id)
                    .order_by(ResearchReport.updated_at.desc())
                )
                reports = result.scalars().all()
                return json.dumps({
                    "reports": [
                        {
                            "id": r.id,
                            "query": r.query,
                            "research_topic": r.research_topic or "",
                            "level": r.level,
                            "status": r.status,
                            "task_id": r.task_id,
                            "created_at": r.created_at.isoformat(),
                        }
                        for r in reports
                    ]
                })
        except Exception as e:
            logger.error(f"Error listing reports: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_research_get_report(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def research_get_report(report_id: int) -> str:
        """Get a research report by ID."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(report_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ResearchReport).where(
                        ResearchReport.id == report_id,
                        ResearchReport.user_id == user_id,
                    )
                )
                report = result.scalars().first()
                if not report:
                    return OperationStatus.error(str(report_id), f"Report {report_id} not found").to_json()
                return json.dumps({
                    "id": report.id,
                    "query": report.query,
                    "research_topic": report.research_topic or "",
                    "report": report.report or "",
                    "notes": json.loads(report.notes_json),
                    "queries": json.loads(report.queries_json),
                    "level": report.level,
                    "status": report.status,
                    "task_id": report.task_id,
                    "created_at": report.created_at.isoformat(),
                })
        except Exception as e:
            logger.error(f"Error getting report: {e}", exc_info=True)
            return OperationStatus.error(str(report_id), str(e)).to_json()


def _register_research_start(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def research_start(
        query: str,
        level: str = "standard",
        max_iterations: int | None = None,
        max_results: int | None = None,
    ) -> str:
        """Start a deep research task (async via Celery)."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        import uuid
        from app.research.state import ResearchLevel, LEVEL_DEFAULTS

        task_id = str(uuid.uuid4())

        try:
            research_level = ResearchLevel(level)
            default_iters, default_results = LEVEL_DEFAULTS.get(research_level, (3, 10))
            effective_iters = max_iterations if max_iterations is not None else default_iters
            effective_res = max_results if max_results is not None else default_results

            async with AsyncSessionLocal() as session:
                report = ResearchReport(
                    user_id=user_id,
                    query=query,
                    level=level,
                    status="running",
                    task_id=task_id,
                    notes_json="[]",
                    queries_json="[]",
                    iterations=effective_iters,
                )
                session.add(report)
                await session.commit()

                from app.research.tasks import process_research
                from app.research.stream import set_processing_flag
                await set_processing_flag(task_id)
                process_research.delay(
                    task_id=task_id,
                    query=query,
                    level=level,
                    max_iterations=effective_iters,
                    max_results=effective_res,
                    user_id=user_id,
                )

                status = OperationStatus(
                    id=task_id,
                    type="research",
                    status="started",
                    message=f"Research started (level={level}, max_iter={effective_iters}). Poll with operation_get_status.",
                    progress=0.0,
                )
                return status.to_json()
        except Exception as e:
            logger.error(f"Error starting research: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_research_get_result(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def research_get_result(task_id: str) -> str:
        """Get the final research result from Redis."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(task_id, "Unauthorized").to_json()

        try:
            from app.research.stream import get_redis
            redis_client = await get_redis()
            key = f"research_result_{task_id}"
            result_json = await redis_client.get(key)
            await redis_client.aclose()

            if result_json:
                data = json.loads(result_json)
                return json.dumps({"result": data})

            # Fall back to DB
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ResearchReport).where(
                        ResearchReport.task_id == task_id,
                        ResearchReport.user_id == user_id,
                    )
                )
                report = result.scalars().first()
                if not report:
                    return OperationStatus.error(task_id, f"Research {task_id} not found").to_json()
                if report.status != "done":
                    return OperationStatus.error(task_id, f"Research not yet complete (status: {report.status})").to_json()
                return json.dumps({"result": {"report": report.report, "topic": report.research_topic}})
        except Exception as e:
            logger.error(f"Error getting research result: {e}", exc_info=True)
            return OperationStatus.error(task_id, str(e)).to_json()


def _register_research_get_state(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def research_get_state(task_id: str) -> str:
        """Get the running state of a research task (for rejoin)."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(task_id, "Unauthorized").to_json()

        try:
            from app.research.stream import get_research_state, get_processing_status
            is_processing = await get_processing_status(task_id)

            if is_processing:
                redis_state = await get_research_state(task_id)
                if redis_state:
                    return json.dumps(redis_state)

            # Fall back to DB
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ResearchReport).where(
                        ResearchReport.task_id == task_id,
                        ResearchReport.user_id == user_id,
                    )
                )
                report = result.scalars().first()
                if not report:
                    return OperationStatus.error(task_id, f"Research {task_id} not found").to_json()
                return json.dumps({
                    "status": report.status,
                    "message": "Research complete" if report.status == "done" else "Research failed",
                    "progress": 1.0,
                    "research_topic": report.research_topic or "",
                    "notes": json.loads(report.notes_json),
                    "queries": json.loads(report.queries_json),
                    "level": report.level,
                    "task_id": task_id,
                })
        except Exception as e:
            logger.error(f"Error getting research state: {e}", exc_info=True)
            return OperationStatus.error(task_id, str(e)).to_json()


def _register_research_delete_report(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def research_delete_report(report_id: int) -> str:
        """Delete a research report."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(report_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ResearchReport).where(
                        ResearchReport.id == report_id,
                        ResearchReport.user_id == user_id,
                    )
                )
                report = result.scalars().first()
                if not report:
                    return OperationStatus.error(str(report_id), f"Report {report_id} not found").to_json()
                await session.delete(report)
                await session.commit()
                return json.dumps({"status": "success", "message": f"Report {report_id} deleted"})
        except Exception as e:
            logger.error(f"Error deleting report: {e}", exc_info=True)
            return OperationStatus.error(str(report_id), str(e)).to_json()


# =============================================================================
# Memory Tools
# =============================================================================

def _register_memory_recall(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def memory_recall(
        workspace_id: int,
        query: str,
        memory_type: str | None = None,
        limit: int = 5,
        use_multi_strategy: bool = False,
    ) -> str:
        """Recall relevant memories for a workspace using semantic search."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(workspace_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                # Verify workspace ownership
                ws_result = await session.execute(
                    select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
                )
                if not ws_result.scalars().first():
                    return OperationStatus.error(str(workspace_id), f"Workspace {workspace_id} not found").to_json()

                from app.memory.service import MemoryService
                service = MemoryService(session)
                results = await service.recall(
                    workspace_id=workspace_id,
                    query=query,
                    memory_type=memory_type,
                    limit=limit,
                    use_multi_strategy=use_multi_strategy,
                )
                return json.dumps({
                    "results": [
                        {
                            "id": r.id,
                            "content": r.content,
                            "memory_type": r.memory_type,
                            "similarity": r.similarity,
                        }
                        for r in results
                    ],
                    "total": len(results),
                    "query": query,
                })
        except Exception as e:
            logger.error(f"Error recalling memories: {e}", exc_info=True)
            return OperationStatus.error(str(workspace_id), str(e)).to_json()


def _register_memory_retain(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def memory_retain(
        workspace_id: int,
        content: str,
        memory_type: str = "fact",
    ) -> str:
        """Store a memory for a workspace."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(workspace_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                # Verify workspace ownership
                ws_result = await session.execute(
                    select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
                )
                if not ws_result.scalars().first():
                    return OperationStatus.error(str(workspace_id), f"Workspace {workspace_id} not found").to_json()

                from app.memory.service import MemoryService
                service = MemoryService(session)
                result = await service.retain(
                    workspace_id=workspace_id,
                    content=content,
                    memory_type=memory_type,
                )
                return json.dumps({
                    "memory_id": result.memory_id,
                    "workspace_id": result.workspace_id,
                    "memory_type": result.memory_type,
                    "created_at": result.created_at.isoformat(),
                })
        except Exception as e:
            logger.error(f"Error retaining memory: {e}", exc_info=True)
            return OperationStatus.error(str(workspace_id), str(e)).to_json()


def _register_memory_get_stats(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def memory_get_stats(workspace_id: int) -> str:
        """Get memory statistics for a workspace."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(workspace_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                # Verify workspace ownership
                ws_result = await session.execute(
                    select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
                )
                if not ws_result.scalars().first():
                    return OperationStatus.error(str(workspace_id), f"Workspace {workspace_id} not found").to_json()

                from app.memory.service import MemoryService
                service = MemoryService(session)
                stats = await service.get_memory_stats(workspace_id)
                return json.dumps(stats)
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}", exc_info=True)
            return OperationStatus.error(str(workspace_id), str(e)).to_json()


def _register_memory_get_entity_memories(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def memory_get_entity_memories(
        workspace_id: int,
        entity_name: str,
        limit: int = 10,
    ) -> str:
        """Get all memories containing a specific entity."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(str(workspace_id), "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                # Verify workspace ownership
                ws_result = await session.execute(
                    select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
                )
                if not ws_result.scalars().first():
                    return OperationStatus.error(str(workspace_id), f"Workspace {workspace_id} not found").to_json()

                from app.memory.service import MemoryService
                service = MemoryService(session)
                results = await service.get_entity_memories(
                    workspace_id=workspace_id,
                    entity_name=entity_name,
                    limit=limit,
                )
                return json.dumps({
                    "entity": entity_name,
                    "memories": [
                        {
                            "id": r.id,
                            "content": r.content,
                            "memory_type": r.memory_type,
                            "similarity": r.similarity,
                        }
                        for r in results
                    ],
                })
        except Exception as e:
            logger.error(f"Error getting entity memories: {e}", exc_info=True)
            return OperationStatus.error(str(workspace_id), str(e)).to_json()


# =============================================================================
# Operation Tools
# =============================================================================

def _register_operation_list(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def operation_list() -> str:
        """List recent active operations for the authenticated user (blackboard, matrix, research)."""
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error("0", "Unauthorized").to_json()

        try:
            async with AsyncSessionLocal() as session:
                # Get recent blackboards
                bb_result = await session.execute(
                    select(BlackboardData)
                    .where(BlackboardData.user_id == user_id)
                    .order_by(BlackboardData.created_at.desc())
                    .limit(10)
                )
                blackboards = bb_result.scalars().all()

                # Get recent matrix analyses
                ma_result = await session.execute(
                    select(MorphologicalAnalysis)
                    .where(MorphologicalAnalysis.user_id == user_id)
                    .order_by(MorphologicalAnalysis.created_at.desc())
                    .limit(10)
                )
                analyses = ma_result.scalars().all()

                # Get recent research reports
                rr_result = await session.execute(
                    select(ResearchReport)
                    .where(ResearchReport.user_id == user_id)
                    .order_by(ResearchReport.created_at.desc())
                    .limit(10)
                )
                reports = rr_result.scalars().all()

                ops = []
                for bb in blackboards:
                    from app.mcp.operations import _map_blackboard_status, _blackboard_progress
                    ops.append({
                        "id": str(bb.id),
                        "type": "blackboard",
                        "status": _map_blackboard_status(bb.status),
                        "progress": _blackboard_progress(bb.status),
                        "created_at": bb.created_at.isoformat(),
                    })
                for ma in analyses:
                    from app.mcp.operations import _map_matrix_status, _matrix_progress
                    ops.append({
                        "id": str(ma.id),
                        "type": "matrix",
                        "status": _map_matrix_status(ma.status),
                        "progress": _matrix_progress(ma.status),
                        "created_at": ma.created_at.isoformat(),
                    })
                for rr in reports:
                    if rr.task_id:
                        ops.append({
                            "id": rr.task_id,
                            "type": "research",
                            "status": "done" if rr.status == "done" else "processing",
                            "progress": 1.0 if rr.status == "done" else 0.5,
                            "created_at": rr.created_at.isoformat(),
                        })

                return json.dumps({"operations": ops})
        except Exception as e:
            logger.error(f"Error listing operations: {e}", exc_info=True)
            return OperationStatus.error("0", str(e)).to_json()


def _register_operation_get_status(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def operation_get_status(task_id: str) -> str:
        """
        Poll the status of any async operation by task_id or record ID.
        """
        user_id = config.user_id_resolver()
        if user_id is None:
            return OperationStatus.error(task_id, "Unauthorized").to_json()

        try:
            status = await get_operation_status(task_id)
            return status.to_json()
        except Exception as e:
            logger.error(f"Error getting operation status: {e}", exc_info=True)
            return OperationStatus.error(task_id, str(e)).to_json()
