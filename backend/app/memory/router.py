"""
Memory API routes.

Provides REST endpoints for memory operations.
"""

from typing import Optional
from uuid import UUID
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_with_schema
from app.auth.models import User
from app.core.security import get_current_user
from app.memory.service import MemoryService, MemoryLimitExceededError
from app.memory.schemas import (
    MemoryCreate,
    MemoryRecallResult,
    RecallResponse,
    RetainResponse,
    RecentMemoriesResponse,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/memory", tags=["memory"])


class RAGIngestRequest(BaseModel):
    """Schema for ingesting a research report into RAG."""
    report_id: int = Field(..., description="Research report ID to ingest")


class RAGQueryRequest(BaseModel):
    """Schema for RAG query."""
    query: str = Field(..., description="Query text")
    limit: int = Field(default=5, ge=1, le=20, description="Max results")
    use_reranker: bool = Field(default=True, description="Use cross-encoder reranking")


async def _verify_workspace_access(
    workspace_id: int,
    db: AsyncSession,
    current_user: User,
) -> None:
    """Verify user has access to the workspace."""
    from app.workspace.models import Workspace
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == current_user.id,
        )
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.post("/{workspace_id}/retain", response_model=RetainResponse)
async def retain_memory(
    workspace_id: int,
    memory: MemoryCreate,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Store a memory for a workspace.

    Args:
        workspace_id: The workspace ID
        memory: Memory content and type

    Returns:
        The created memory info
    """
    service = MemoryService(db)
    try:
        result = await service.retain(
            workspace_id=workspace_id,
            content=memory.content,
            memory_type=memory.memory_type,
            metadata=memory.extra_data,
        )
        return result
    except MemoryLimitExceededError as e:
        raise HTTPException(status_code=507, detail=str(e))


@router.post("/{workspace_id}/recall", response_model=RecallResponse)
async def recall_memories(
    workspace_id: int,
    query: str = Query(..., description="Search query"),
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    limit: int = Query(5, ge=1, le=20, description="Max results"),
    max_tokens: int = Query(4000, ge=100, le=10000, description="Max token budget"),
    use_multi_strategy: bool = Query(False, description="Use multi-strategy retrieval (semantic + keyword)"),
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Recall relevant memories for a workspace.

    Uses vector similarity search to find memories related to the query.

    Args:
        workspace_id: The workspace ID
        query: Search query
        memory_type: Optional filter by memory type
        limit: Maximum number of results
        max_tokens: Maximum token budget for results
        use_multi_strategy: If True, combines semantic + keyword search with RRF fusion

    Returns:
        List of relevant memories
    """
    service = MemoryService(db)
    results = await service.recall(
        workspace_id=workspace_id,
        query=query,
        memory_type=memory_type,
        limit=limit,
        max_tokens=max_tokens,
        use_multi_strategy=use_multi_strategy,
    )
    return RecallResponse(
        results=results,
        total=len(results),
        query=query,
    )


@router.get("/{workspace_id}/entities/{entity_name}")
async def get_entity_memories(
    workspace_id: int,
    entity_name: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Get all memories containing a specific entity.

    Args:
        workspace_id: The workspace ID
        entity_name: The entity name to search for
        limit: Maximum number of results

    Returns:
        List of memories containing the entity
    """
    service = MemoryService(db)
    results = await service.get_entity_memories(
        workspace_id=workspace_id,
        entity_name=entity_name,
        limit=limit,
    )
    return {"entity": entity_name, "memories": results}


@router.get("/{workspace_id}/stats")
async def get_memory_stats(
    workspace_id: int,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Get memory statistics for a workspace.

    Args:
        workspace_id: The workspace ID

    Returns:
        Memory counts by type
    """
    service = MemoryService(db)
    stats = await service.get_memory_stats(workspace_id)
    return stats


@router.post("/{workspace_id}/preference")
async def update_preference(
    workspace_id: int,
    preference_key: str = Query(..., description="Preference name"),
    preference_value: str = Query(..., description="Preference value"),
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Update a user preference.

    Preference memories are stored with type='preference' and overwrite
    previous values with the same key.

    Args:
        workspace_id: The workspace ID
        preference_key: The preference name
        preference_value: The preference value

    Returns:
        The created memory info
    """
    service = MemoryService(db)
    result = await service.update_preference(
        workspace_id=workspace_id,
        preference_key=preference_key,
        preference_value=preference_value,
    )
    return result


@router.get("/{workspace_id}/recent", response_model=RecentMemoriesResponse)
async def get_recent_memories(
    workspace_id: int,
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Get recent memories for a workspace.

    Args:
        workspace_id: The workspace ID
        limit: Maximum number of results

    Returns:
        List of recent memories
    """
    service = MemoryService(db)
    memories = await service.get_recent_memories(workspace_id, limit=limit)
    return RecentMemoriesResponse(memories=memories, total=len(memories))


@router.get("/{workspace_id}/hit-rate")
async def get_memory_hit_rate(
    workspace_id: int,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Get memory hit rate for a workspace.

    Hit rate = memories that have been recalled at least once / total memories.

    Args:
        workspace_id: The workspace ID

    Returns:
        Hit rate as a float between 0 and 1
    """
    service = MemoryService(db)
    hit_rate = await service.get_hit_rate(workspace_id)
    return {"hit_rate": hit_rate}


@router.post("/{workspace_id}/rag/ingest")
async def ingest_research_for_rag(
    workspace_id: int,
    request: RAGIngestRequest,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    """
    Ingest a research report into memory for RAG.

    Chunks the research report content and stores it as memory units
    with embeddings for vector search.

    Args:
        workspace_id: The workspace ID
        request: Contains report_id to ingest

    Returns:
        Number of chunks ingested
    """
    await _verify_workspace_access(workspace_id, db, current_user)

    from app.research.models import ResearchReport

    # Fetch the research report
    result = await db.execute(
        select(ResearchReport).where(ResearchReport.id == request.report_id)
    )
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Research report not found")

    if report.report is None or report.report == "":
        raise HTTPException(status_code=400, detail="Research report has no content")

    # Chunk the report content
    chunk_size = 1000  # characters
    overlap = 200  # overlap between chunks
    chunks = []
    content = report.report

    if len(content) <= chunk_size:
        chunks.append(content)
    else:
        start = 0
        while start < len(content):
            end = start + chunk_size
            # Try to break at sentence boundary
            if end < len(content):
                for sep in ['。', '！', '？', '.', '!', '?', '\n']:
                    last_sep = content.rfind(sep, start, end)
                    if last_sep > start:
                        end = last_sep + 1
                        break
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - overlap
            if start < 0:
                start = 0

    # Store chunks as memory units
    service = MemoryService(db)
    bank = await service.ensure_bank(workspace_id)

    from app.memory.models import MemoryUnit

    # Check if already ingested by looking for memories with this report's metadata
    existing_result = await db.execute(
        select(func.count(MemoryUnit.id)).where(
            MemoryUnit.bank_id == bank.id,
            MemoryUnit.extra_data.contains({"source": "research", "report_id": str(report.id)})
        )
    )
    existing_count = existing_result.scalar() or 0

    if existing_count > 0:
        return {
            "status": "already_ingested",
            "chunks": existing_count,
            "message": f"Report already ingested ({existing_count} chunks)"
        }

    # Ingest each chunk
    ingested = 0
    try:
        if service.embedding is None:
            from app.memory.embedding import get_embedding_service
            service.embedding = get_embedding_service()

        for idx, chunk_text in enumerate(chunks):
            # Generate embedding
            try:
                embedding = service.embedding.encode([chunk_text])[0]
            except Exception as e:
                logger.warning(f"Failed to generate embedding for chunk {idx}: {e}")
                embedding = None

            memory = MemoryUnit(
                bank_id=bank.id,
                content=chunk_text,
                embedding=embedding,
                memory_type="context",
                extra_data={
                    "source": "research",
                    "report_id": str(report.id),
                    "chunk_index": idx,
                    "research_topic": report.research_topic or report.query,
                },
                entity_ids=[],
            )
            db.add(memory)
            ingested += 1

        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to ingest: {str(e)}")

    return {
        "status": "success",
        "chunks": ingested,
        "message": f"Ingested {ingested} chunks from research report"
    }


@router.post("/{workspace_id}/rag/query")
async def query_rag(
    workspace_id: int,
    request: RAGQueryRequest,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    """
    Query RAG memories for a workspace.

    Searches memories created from research reports using multi-strategy retrieval
    (vector + BM25) with optional cross-encoder reranking.

    Args:
        workspace_id: The workspace ID
        request: Contains query, limit, and use_reranker flag

    Returns:
        List of relevant memory chunks
    """
    await _verify_workspace_access(workspace_id, db, current_user)

    service = MemoryService(db)

    # Use multi-strategy recall with reranking for best results
    results = await service.recall(
        workspace_id=workspace_id,
        query=request.query,
        memory_type="context",  # Only search context (RAG) memories
        limit=request.limit,
        use_multi_strategy=True,
        use_reranker=request.use_reranker,
    )

    return {
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "memory_type": r.memory_type,
                "similarity": r.similarity,
                "source": r.metadata.get("source") if r.metadata else None,
            }
            for r in results
        ],
        "query": request.query,
        "total": len(results)
    }
