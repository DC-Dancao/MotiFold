"""Organization CRUD router with async provisioning."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.core.database import get_db
from app.auth.models import User
from app.org.models import Organization, OrganizationMember
from app.org.schemas import OrganizationCreate, OrganizationOut, OrganizationMemberCreate, OrganizationMemberOut, OrgMemberWithUser
from app.org.dependencies import require_org_role
from app.core.security import get_current_user

router = APIRouter()

@router.post("/", response_model=OrganizationOut)
async def create_organization(
    org_data: OrganizationCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check slug uniqueness
    result = await db.execute(select(Organization).where(Organization.slug == org_data.slug))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Slug already taken")

    org = Organization(
        name=org_data.name,
        slug=org_data.slug,
        status='provisioning'
    )
    db.add(org)
    await db.flush()  # Get the org.id

    member = OrganizationMember(
        id=f"{org.id}_{current_user.id}",
        organization_id=org.id,
        user_id=current_user.id,
        role="owner"
    )
    db.add(member)
    await db.commit()
    await db.refresh(org)

    # Trigger async provisioning
    from app.org import provisioner
    background_tasks.add_task(provisioner.provision_org_schema, org_data.slug)

    return org

@router.get("/", response_model=List[OrganizationOut])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Organization)
        .join(OrganizationMember)
        .where(OrganizationMember.user_id == current_user.id)
    )
    return result.scalars().all()

@router.get("/{org_id}", response_model=OrganizationOut)
async def get_organization(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_org_role("owner", "admin", "member")),
):
    result = await db.execute(select(Organization).where(Organization.slug == org_id))
    org = result.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if org.status == 'failed':
        raise HTTPException(status_code=503, detail="Organization provisioning failed")
    return org

@router.get("/{org_id}/members", response_model=List[OrgMemberWithUser])
async def list_org_members(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_org_role("owner", "admin", "member")),
):
    from app.auth.models import User as UserModel
    result = await db.execute(
        select(OrganizationMember, UserModel)
        .join(UserModel, OrganizationMember.user_id == UserModel.id)
        .where(OrganizationMember.organization_id == org_id)
    )
    rows = result.all()
    return [
        OrgMemberWithUser(
            id=om.id,
            organization_id=om.organization_id,
            user_id=om.user_id,
            role=om.role,
            joined_at=om.joined_at,
            username=u.username,
            email=getattr(u, 'email', None),
        )
        for om, u in rows
    ]

@router.post("/{org_id}/members", response_model=OrganizationMemberOut)
async def invite_org_member(
    org_id: str,
    member_data: OrganizationMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_org_role("owner", "admin")),
):
    from app.auth.models import User as UserModel
    user_result = await db.execute(select(UserModel).where(UserModel.id == member_data.user_id))
    if not user_result.scalars().first():
        raise HTTPException(status_code=404, detail="User not found")

    existing = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == member_data.user_id,
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="User is already a member")

    new_member = OrganizationMember(
        id=f"{org_id}_{member_data.user_id}",
        organization_id=org_id,
        user_id=member_data.user_id,
        role=member_data.role,
    )
    db.add(new_member)
    await db.commit()
    await db.refresh(new_member)
    return new_member

@router.delete("/{org_id}/members/{user_id}")
async def remove_org_member(
    org_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_org_role("owner", "admin")),
):
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    member = result.scalars().first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove organization owner")

    await db.delete(member)
    await db.commit()
    return {"status": "success"}
