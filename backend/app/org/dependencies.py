"""FastAPI dependencies for org membership validation."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.auth.models import User
from app.org.models import Organization, OrganizationMember
from app.core.security import get_current_user
from app.tenant.context import get_current_org

async def get_current_org_membership(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationMember:
    """Validates user is member of current org from X-Org-ID header."""
    org_slug = get_current_org()
    if org_slug is None:
        raise HTTPException(status_code=400, detail="X-Org-ID header required")

    # Check org status
    result = await db.execute(
        select(Organization).where(Organization.id == org_slug)
    )
    org = result.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if org.status != 'active':
        raise HTTPException(status_code=503, detail="Organization not active")

    # Check membership
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_slug,
            OrganizationMember.user_id == str(current_user.id)
        )
    )
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return membership

def require_org_role(*roles: str):
    """Dependency factory for role-based access."""
    async def checker(
        membership: OrganizationMember = Depends(get_current_org_membership),
    ) -> OrganizationMember:
        if membership.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return membership
    return checker
