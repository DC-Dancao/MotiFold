# Multi-Tenancy Implementation Plan (Separate Schema)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Organization support with **per-org database schemas**. Each org has its own schema (`org_{slug}`) containing workspaces, chats, etc. Shared data (users, orgs, memberships) lives in `public` schema.

**Architecture:**
- `public` schema: `users`, `organizations`, `organization_members`
- `org_{slug}` schema: `workspaces`, `chats`, `blackboards`, etc.
- Org provisioning: async with status polling (`provisioning` → `active`)
- Query routing: `SET search_path TO org_{slug}, public`

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Celery (for async provisioning)

---

## File Map

### New Files
- `backend/app/tenant/context.py` — already exists, update to handle slug→schema mapping
- `backend/app/tenant/middleware.py` — update to SET search_path
- `backend/app/org/models.py` — Organization, OrganizationMember in public schema
- `backend/app/org/schemas.py` — Pydantic schemas
- `backend/app/org/dependencies.py` — org membership validation
- `backend/app/org/router.py` — CRUD + provisioning
- `backend/app/org/provisioner.py` — Celery task for async schema creation
- `backend/app/workspace/members.py` — WorkspaceMember model
- `backend/migrations/versions/xxx_split_into_public_and_org_schema.py` — Split schema migration

### Modified Files
- `backend/app/auth/models.py` — Add UUID primary key (keep Integer for backward compat)
- `backend/app/workspace/models.py` — Move to org schema pattern
- `backend/app/workspace/router.py` — Update for org-scoped queries
- `backend/app/chat/router.py` — Update for org-scoped queries
- `backend/app/blackboard/router.py` — Update for org-scoped queries
- `backend/app/matrix/router.py` — Update for org-scoped queries
- `backend/app/research/router.py` — Update for org-scoped queries
- `backend/app/main.py` — Register org router, tenant middleware
- `backend/tests/test_org.py` — Tests

---

## Task 1: Database Migration — Split into Public and Org Schemas

**Files:**
- Create: `backend/migrations/versions/xxx_split_into_public_and_org_schema.py`

- [ ] **Step 1: Create migration to set up public schema tables**

```python
"""Split into public and org schemas

Revision ID: xxx
Revises: c71cbe4e716d
Create Date: 2026-04-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'xxx'
down_revision: Union[str, None] = 'c71cbe4e716d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # organizations table (in public schema - already created in previous migration)
    # But add status column for async provisioning
    op.add_column('organizations',
        sa.Column('status', sa.String(), nullable=False, server_default='active'))

    # Add slug index if not exists
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)

    # organization_members already exists from previous migration
    # Just need to update foreign key to use UUID if users.id becomes UUID

    # Create a template schema for new orgs (this is the reference for LIKE)
    # Note: We don't create the actual org schemas here - that's done at runtime
    # This migration just sets up the public schema structure

    # Add org_id columns (using slug, not id) to resource tables
    op.add_column('workspaces', sa.Column('org_slug', sa.String(), sa.ForeignKey('organizations.slug', ondelete='CASCADE'), nullable=True))
    op.create_index(op.f('ix_workspaces_org_slug'), 'workspaces', ['org_slug'])

def downgrade() -> None:
    op.drop_index(op.f('ix_workspaces_org_slug'))
    op.drop_column('workspaces', 'org_slug')
    op.drop_column('organizations', 'status')
```

**Important note:** This migration continues from `c71cbe4e716d` (the previous migration that added org tables with Integer PKs). For now we use the existing tables and add `org_slug` column to workspaces.

- [ ] **Step 2: Commit migration**

```bash
git add backend/migrations/versions/xxx_split_into_public_and_org_schema.py
git commit -m "db: Add organizations status column and org_slug to workspaces"
```

---

## Task 2: Tenant Middleware with Search Path

**Files:**
- Modify: `backend/app/tenant/context.py`
- Modify: `backend/app/tenant/middleware.py`

- [ ] **Step 1: Update tenant context to handle slug→schema mapping**

```python
# backend/app/tenant/context.py
from contextvars import ContextVar
from typing import Optional

_current_org_slug: ContextVar[Optional[str]] = ContextVar('current_org_slug', default=None)

def set_current_org(org_slug: Optional[str]) -> None:
    _current_org_slug.set(org_slug)

def get_current_org() -> Optional[str]:
    return _current_org_slug.get()

def get_schema_name(org_slug: str) -> str:
    """Convert org slug to schema name."""
    return f"org_{org_slug}"

def clear_current_org() -> None:
    _current_org_slug.set(None)
```

- [ ] **Step 2: Update middleware to SET search_path**

```python
# backend/app/tenant/middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import HTTPException
from app.tenant.context import set_current_org, clear_current_org, get_schema_name
from sqlalchemy import text

HEADER_ORG_ID = "x-org-id"

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        org_slug = request.headers.get(HEADER_ORG_ID)

        if org_slug:
            # Validate slug format (alphanumeric + underscore only)
            if not org_slug.replace('_', '').replace('-', '').isalnum():
                raise HTTPException(status_code=400, detail="Invalid org slug")
            set_current_org(org_slug)

            # Also set PostgreSQL search_path if we have a DB connection in request state
            # This will be used in the database dependency
            request.state.org_schema = get_schema_name(org_slug)
        else:
            set_current_org(None)
            request.state.org_schema = None

        try:
            response = await call_next(request)
            return response
        finally:
            clear_current_org()
```

- [ ] **Step 3: Update database dependency to use search_path**

Modify `backend/app/core/database.py` — add a function to get the schema-scoped session:

```python
# Add to database.py
async def get_db_with_schema(request: Request):
    """Get DB session with search_path set to org schema if applicable."""
    async with AsyncSessionLocal() as session:
        org_schema = getattr(request.state, 'org_schema', None)
        if org_schema:
            await session.execute(text(f"SET search_path TO {org_schema}, public"))
        yield session
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/tenant/context.py backend/app/tenant/middleware.py backend/app/core/database.py
git commit -m "feat: Update tenant middleware for schema-based multi-tenancy"
```

---

## Task 3: Org Module — Models, Schemas, Dependencies, Router

**Files:**
- Create: `backend/app/org/models.py`
- Create: `backend/app/org/schemas.py`
- Create: `backend/app/org/dependencies.py`
- Create: `backend/app/org/router.py`

- [ ] **Step 1: Write org models (public schema)**

```python
# backend/app/org/models.py
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {'schema': 'public'}

    id = Column(String, primary_key=True)  # Use slug as ID for simplicity
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, nullable=False, default='active')  # provisioning, active, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")

class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = {'schema': 'public'}

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("public.organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False, default="member")  # owner, admin, member
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (UniqueConstraint('organization_id', 'user_id', name='uq_org_member'),)
```

- [ ] **Step 2: Write org schemas**

```python
# backend/app/org/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class OrganizationCreate(BaseModel):
    name: str
    slug: str  # Will be used as schema name: org_{slug}

class OrganizationOut(BaseModel):
    id: str  # slug is the ID
    name: str
    slug: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class OrganizationMemberCreate(BaseModel):
    user_id: str
    role: str = "member"

class OrganizationMemberOut(BaseModel):
    id: str
    organization_id: str
    user_id: str
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True

class OrgMemberWithUser(OrganizationMemberOut):
    username: str
    email: Optional[str] = None
```

- [ ] **Step 3: Write org dependencies**

```python
# backend/app/org/dependencies.py
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.auth.models import User
from app.org.models import Organization, OrganizationMember
from app.tenant.context import get_current_org

async def get_current_org_membership(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(lambda: None),
) -> OrganizationMember:
    """Validates user is member of current org from X-Org-ID header."""
    org_slug = get_current_org()
    if org_slug is None:
        raise HTTPException(status_code=400, detail="X-Org-ID header required")

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
```

- [ ] **Step 4: Write org router**

```python
# backend/app/org/router.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import re

from app.core.database import get_db
from app.auth.models import User
from app.org.models import Organization, OrganizationMember
from app.org.schemas import OrganizationCreate, OrganizationOut, OrganizationMemberCreate, OrganizationMemberOut, OrgMemberWithUser
from app.org.dependencies import require_org_role
from app.core.security import get_current_user

router = APIRouter()

SLUG_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]*$')

def validate_slug(slug: str) -> bool:
    """Validate org slug format: lowercase alphanumeric + underscore/dash"""
    return bool(SLUG_PATTERN.match(slug)) and len(slug) <= 50

@router.post("/", response_model=OrganizationOut)
async def create_organization(
    org_data: OrganizationCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate slug format
    if not validate_slug(org_data.slug):
        raise HTTPException(status_code=400, detail="Invalid slug format. Use lowercase letters, numbers, and underscores.")

    # Check slug uniqueness
    result = await db.execute(select(Organization).where(Organization.id == org_data.slug))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Slug already taken")

    org = Organization(
        id=org_data.slug,  # Use slug as primary key
        name=org_data.name,
        slug=org_data.slug,
        status='provisioning'
    )
    db.add(org)

    # Add creator as owner
    member = OrganizationMember(
        id=f"{org_data.slug}_{current_user.id}",
        organization_id=org_data.slug,
        user_id=str(current_user.id),
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
        .where(OrganizationMember.user_id == str(current_user.id))
    )
    return result.scalars().all()

@router.get("/{org_id}", response_model=OrganizationOut)
async def get_organization(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_org_role("owner", "admin", "member")),
):
    result = await db.execute(select(Organization).where(Organization.id == org_id))
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
    result = await db.execute(
        select(OrganizationMember, User)
        .join(User, OrganizationMember.user_id == User.id)
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
    user_result = await db.execute(select(User).where(User.id == member_data.user_id))
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
```

- [ ] **Step 5: Write org provisioner using Alembic API**

**Approach:** Use Alembic's Python API to run migrations against the new org schema. This keeps all DDL in Alembic version control instead of duplicating it in code.

First, create a dedicated migration for org tables:

```python
# backend/migrations/versions/xxx_create_org_schema_tables.py
"""Create tables in org schema

This migration is run against each new org schema during provisioning.
It creates all business tables (workspaces, chats, etc.) that live in org schemas.
The public schema tables (organizations, organization_members) are created separately.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'xxx'
down_revision: Union[str, None] = None  # This is run standalone per schema
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # All tables go into the org schema (set by Alembic config when this is run)
    op.create_table('workspaces',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(), nullable=False, server_default='My Workspace'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_table('chats',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(), server_default='New Chat'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    # ... other tables (blackboards, keywords, morphological_analyses, research_reports)
```

Then the provisioner uses Alembic API:

```python
# backend/app/org/provisioner.py
from alembic.config import Config as AlembicConfig
from alembic import command
from sqlalchemy import text
from app.core.database import engine, AsyncSessionLocal
import logging

logger = logging.getLogger(__name__)

async def provision_org_schema(org_slug: str) -> None:
    """
    Provision a new org schema using Alembic:
    1. CREATE SCHEMA org_{slug}
    2. Run Alembic migration against new schema (creates all business tables)
    3. Update organizations.status to 'active'
    """
    schema_name = f"org_{org_slug}"

    try:
        # Step 1: Create schema
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

        # Step 2: Run Alembic migration against new schema
        # We use a modified Alembic config that sets the default schema
        alembic_cfg = AlembicConfig()
        alembic_cfg.set_main_option('sqlalchemy.url', str(engine.url))

        # Override the schema search_path for this migration
        # Alembic will use this as the target schema
        with engine.connect() as conn:
            # Set search_path for this connection
            conn.execute(text(f'SET search_path TO "{schema_name}", public'))
            conn.commit()

            # Run the org-specific migration
            # We need to use Alembic's programmatic API
            from alembic.runtime.migration import MigrationContext
            from alembic.script import ScriptDirectory

            script_dir = ScriptDirectory.from_config(alembic_cfg)
            migration_context = MigrationContext.configure(
                connection=conn.sync_connection,
                opts={
                    'script': script_dir,
                    'destination_rev': None,
                    'upgrade_token': 'head',
                }
            )

            # Get our org schema migration
            migration = script_dir.get_revision('xxx')  # revision from create_org_schema_tables.py

            # Run upgrade
            migration_context.run_migration([migration])

        # Step 3: Update status
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE public.organizations SET status = 'active' WHERE id = :id"),
                {"id": org_slug}
            )
            await session.commit()

        logger.info(f"Successfully provisioned schema for org {org_slug}")

    except Exception as e:
        logger.error(f"Failed to provision schema for org {org_slug}: {e}")
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE public.organizations SET status = 'failed' WHERE id = :id"),
                {"id": org_slug}
            )
            await session.commit()
        raise
```

**Why this approach:**
- All DDL lives in Alembic migrations (single source of truth)
- Alembic's transaction handling is used correctly
- No duplication between migration files and code
- Schema changes are version-controlled and reversible

- [ ] **Step 6: Commit**

```bash
git add backend/app/org/
git commit -m "feat: Add Organization module with async schema provisioning"
```

---

## Task 4: Update Main App — Register Middleware and Router

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add imports and register**

After existing imports, add:
```python
from app.tenant.middleware import TenantMiddleware
from app.org.router import router as org_router
```

Register middleware (add before other middleware):
```python
app.add_middleware(TenantMiddleware)
```

Register org router:
```python
app.include_router(org_router, prefix="/api/orgs", tags=["organizations"])
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: Register tenant middleware and org router"
```

---

## Task 5: Write Org Feature Tests

**Files:**
- Create: `backend/tests/test_org.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_org.py
import pytest
from httpx import AsyncClient
from app.main import app
from app.auth.models import User
from app.org.models import Organization, OrganizationMember
from app.core.database import AsyncSessionLocal

class TestOrgCreation:
    async def test_create_org_valid_slug(self, client: AsyncClient, db_session):
        response = await client.post(
            "/api/orgs/",
            json={"name": "My Org", "slug": "my-org"},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Org"
        assert data["slug"] == "my-org"
        assert data["status"] == "provisioning"

    async def test_create_org_invalid_slug(self, client: AsyncClient, db_session):
        response = await client.post(
            "/api/orgs/",
            json={"name": "My Org", "slug": "MyOrg!@#"},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 400

    async def test_create_org_duplicate_slug(self, client: AsyncClient, db_session, setup_org):
        response = await client.post(
            "/api/orgs/",
            json={"name": "Another Org", "slug": "test-org"},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 400

class TestOrgMembership:
    async def test_list_orgs(self, client: AsyncClient, setup_org):
        response = await client.get(
            "/api/orgs/",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        assert len(response.json()) >= 1

    async def test_get_org_requires_membership(self, client: AsyncClient, setup_org):
        response = await client.get(
            f"/api/orgs/{setup_org.id}",
            headers={"Authorization": f"Bearer {other_user_token}"}
        )
        assert response.status_code == 403

    async def test_invite_member(self, client: AsyncClient, setup_org, db_session):
        response = await client.post(
            f"/api/orgs/{setup_org.id}/members",
            json={"user_id": other_user.id, "role": "member"},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200

    async def test_remove_member(self, client: AsyncClient, setup_org, db_session):
        await client.post(
            f"/api/orgs/{setup_org.id}/members",
            json={"user_id": other_user.id, "role": "member"},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response = await client.delete(
            f"/api/orgs/{setup_org.id}/members/{other_user.id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/test_org.py
git commit -m "test: Add organization feature tests"
```

---

## Spec Coverage Check

| Spec Section | Tasks |
|--------------|-------|
| Separate schema architecture | Task 1, 2, 3 |
| public/organizations, organization_members | Task 1, 3 |
| org_{slug} schema with workspaces, chats, etc. | Task 3 (provisioner) |
| Async provisioning with status polling | Task 3 |
| X-Org-ID header + search_path | Task 2 |
| Org-level roles (owner/admin/member) | Task 3 |
| Workspace-level roles | Task 3 (future) |
| API endpoints | Task 3 |

---

## Self-Review

- [ ] All file paths are exact
- [ ] All code blocks are complete (no placeholders)
- [ ] Uses slug as org ID (not integer)
- [ ] Provisioning is async with status field
- [ ] Schema name format: `org_{slug}`
- [ ] search_path set to `org_{slug}, public`

**Plan complete.** Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
