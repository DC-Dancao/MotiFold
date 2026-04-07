from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import List

from app.database import get_db
from app.models import User, Workspace
from app.schemas import WorkspaceCreate, WorkspaceOut
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[WorkspaceOut])
async def list_workspaces(
    skip: int = 0, limit: int = 20, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Workspace).where(Workspace.user_id == current_user.id).order_by(desc(Workspace.created_at)).offset(skip).limit(limit)
    )
    return result.scalars().all()

@router.post("/", response_model=WorkspaceOut)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    new_workspace = Workspace(user_id=current_user.id, name=workspace_data.name)
    db.add(new_workspace)
    await db.commit()
    await db.refresh(new_workspace)
    return new_workspace

@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: int, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == current_user.id))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace

@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: int, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == current_user.id))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    await db.delete(workspace)
    await db.commit()
    return {"status": "success", "message": "Workspace deleted"}
