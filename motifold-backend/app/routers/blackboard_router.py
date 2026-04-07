import json
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.auth import get_current_user
from app.models import BlackboardData
from app.worker import generate_blackboard_task

router = APIRouter(
    prefix="/blackboard",
    tags=["blackboard"],
    responses={404: {"description": "Not found"}},
)

class BlackboardCreate(BaseModel):
    topic: str
    workspace_id: Optional[int] = None

class BlackboardResponse(BaseModel):
    id: int
    topic: str
    status: str
    content_json: str
    created_at: str

@router.post("/", response_model=BlackboardResponse)
async def create_blackboard(bb_create: BlackboardCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
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
    
    # Trigger Celery Task
    generate_blackboard_task.delay(new_bb.id, bb_create.topic)
    
    return BlackboardResponse(
        id=new_bb.id,
        topic=new_bb.topic,
        status=new_bb.status,
        content_json=new_bb.content_json,
        created_at=new_bb.created_at.isoformat()
    )

@router.get("/history", response_model=List[BlackboardResponse])
async def get_blackboard_history(
    workspace_id: Optional[int] = None, 
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_user)
):
    """
    获取用户的黑板历史记录
    """
    from sqlalchemy.future import select
    query = select(BlackboardData).filter(BlackboardData.user_id == current_user.id)
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
async def get_blackboard(bb_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    获取单个黑板的详细数据
    """
    from sqlalchemy.future import select
    query = select(BlackboardData).filter(BlackboardData.id == bb_id, BlackboardData.user_id == current_user.id)
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
async def delete_blackboard(bb_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    删除黑板记录
    """
    from sqlalchemy.future import select
    query = select(BlackboardData).filter(BlackboardData.id == bb_id, BlackboardData.user_id == current_user.id)
    result = await db.execute(query)
    bb = result.scalars().first()
    
    if not bb:
        raise HTTPException(status_code=404, detail="Blackboard not found")
        
    await db.delete(bb)
    await db.commit()
    return {"message": "Deleted successfully"}
