import json
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_db_with_schema
from app.core.security import get_current_user
from app.blackboard.models import BlackboardData
from app.blackboard.schemas import BlackboardCreate, BlackboardResponse
from app.org.dependencies import get_current_org_membership
from app.tenant.context import get_current_org

router = APIRouter(
    prefix="/blackboard",
    tags=["blackboard"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=BlackboardResponse)
async def create_blackboard(
    bb_create: BlackboardCreate,
    request: Request,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    """
    创建一个新的黑板生成任务
    """
    new_bb = BlackboardData(
        user_id=current_user.id,
        workspace_id=bb_create.workspace_id,
        topic=bb_create.topic,
        status="pending",
        content_json="[]"
    )
    db.add(new_bb)
    await db.commit()
    await db.refresh(new_bb)

    from app.worker.blackboard_tasks import generate_blackboard_task
    org_schema = getattr(request.state, 'org_schema', None)
    generate_blackboard_task.delay(new_bb.id, bb_create.topic, org_schema)

    return BlackboardResponse(
        id=new_bb.id,
        topic=new_bb.topic,
        status=new_bb.status,
        content_json=new_bb.content_json,
        created_at=new_bb.created_at.isoformat()
    )

@router.get("/history", response_model=List[BlackboardResponse])
async def get_blackboard_history(
    request: Request,
    workspace_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    """
    获取用户的黑板历史记录
    """
    query = select(BlackboardData)
    if workspace_id:
        query = query.filter(BlackboardData.workspace_id == workspace_id)

    query = query.order_by(BlackboardData.created_at.desc())
    result = await db.execute(query)
    records = result.scalars().all()

    return [
        BlackboardResponse(
            id=r.id,
            topic=r.topic,
            status=r.status,
            content_json=r.content_json,
            created_at=r.created_at.isoformat()
        ) for r in records
    ]

@router.get("/{bb_id}", response_model=BlackboardResponse)
async def get_blackboard(
    bb_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    """
    获取单个黑板的详细数据
    """
    query = select(BlackboardData).filter(BlackboardData.id == bb_id)
    result = await db.execute(query)
    bb = result.scalars().first()

    if not bb:
        raise HTTPException(status_code=404, detail="Blackboard not found")

    return BlackboardResponse(
        id=bb.id,
        topic=bb.topic,
        status=bb.status,
        content_json=bb.content_json,
        created_at=bb.created_at.isoformat()
    )

@router.delete("/{bb_id}")
async def delete_blackboard(
    bb_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    """
    删除黑板记录
    """
    query = select(BlackboardData).filter(BlackboardData.id == bb_id)
    result = await db.execute(query)
    bb = result.scalars().first()

    if not bb:
        raise HTTPException(status_code=404, detail="Blackboard not found")

    await db.delete(bb)
    await db.commit()
    return {"message": "Deleted successfully"}
