from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import List

from app.core.database import get_db, get_db_with_schema
from app.auth.models import User
from app.workspace.models import Workspace
from app.workspace.schemas import WorkspaceCreate, WorkspaceOut
from app.core.security import get_current_user
from app.org.dependencies import get_current_org_membership
from app.tenant.context import get_current_org

router = APIRouter()

@router.get("/", response_model=List[WorkspaceOut])
async def list_workspaces(
    request: Request,
    skip: int = 0, limit: int = 20,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    org_slug = get_current_org()
    result = await db.execute(
        select(Workspace)
        .where(Workspace.org_slug == org_slug)
        .order_by(desc(Workspace.created_at))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

@router.post("/", response_model=WorkspaceOut)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    org_slug = get_current_org()
    new_workspace = Workspace(
        user_id=current_user.id,
        org_slug=org_slug,
        name=workspace_data.name
    )
    db.add(new_workspace)
    await db.commit()
    return new_workspace

@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace

@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == current_user.id))
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    await db.delete(workspace)
    await db.commit()
    return {"status": "success", "message": "Workspace deleted"}
