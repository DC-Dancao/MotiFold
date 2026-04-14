from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request, Response, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
import secrets
import hashlib
import string

from app.core.database import get_db
from app.auth.models import User, ApiKey
from app.auth.schemas import UserCreate, UserOut, Token
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token, _get_user_by_token
from app.core.config import settings

class RefreshRequest(BaseModel):
    refresh_token: str | None = None

router = APIRouter()

@router.post("/register", response_model=UserOut)
async def register(user: UserCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user.username))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, password_hash=hashed_password)
    db.add(db_user)
    await db.flush()  # Get the user.id

    # Create default personal organization for the user
    # Note: All data is in public schema (not separate org schemas)
    from app.org.models import Organization, OrganizationMember
    org_slug = f"user_{db_user.id}"
    org = Organization(
        name=f"{db_user.username}'s Organization",
        slug=org_slug,
        status='provisioning'
    )
    db.add(org)
    await db.flush()  # Get the org.id

    member = OrganizationMember(
        id=f"{org.id}_{db_user.id}",
        organization_id=org.id,
        user_id=db_user.id,
        role="owner"
    )
    db.add(member)
    await db.commit()

    # Trigger async schema provisioning (instant via template clone)
    from app.org import provisioner
    background_tasks.add_task(provisioner.provision_org_schema, org_slug)

    await db.refresh(db_user)

    return db_user

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "refresh_token": refresh_token
    }

@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    refresh_request: RefreshRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    refresh_token_value = None
    if refresh_request and refresh_request.refresh_token:
        refresh_token_value = refresh_request.refresh_token
    else:
        refresh_token_value = request.cookies.get("motifold_refresh_token")

    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await _get_user_by_token(refresh_token_value, db, token_type="refresh")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Optional: return a new refresh token as well, for rotating refresh tokens
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_refresh_token = create_refresh_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )
    
    secure = settings.COOKIE_SECURE

    response.set_cookie(
        "motifold_token",
        access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 7,
    )
    response.set_cookie(
        "motifold_refresh_token",
        new_refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 30,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": new_refresh_token
    }


class ApiKeyCreate(BaseModel):
    name: str | None = None
    expires_days: int | None = None  # None = never expires


class ApiKeyOut(BaseModel):
    id: int
    key_id: str
    key_prefix: str
    name: str | None
    organization_id: int
    expires_at: str | None
    created_at: str


class ApiKeyCreated(BaseModel):
    """Only returned once when created."""
    key: str  # the full API key (only time it's returned)
    key_id: str
    key_prefix: str


def _extract_bearer_or_cookie_token(request: Request) -> str:
    """Extract token from Authorization header or fallback to cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    # Fallback to cookie (like get_current_user does)
    token = request.cookies.get("motifold_token")
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token required")
    return token


@router.post("/api-key", response_model=ApiKeyCreated)
async def create_api_key(
    request: Request,
    api_key_request: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a new API key for programmatic access.
    The full key is only returned once — save it securely.
    """
    try:
        token = _extract_bearer_or_cookie_token(request)
        user = await _get_user_by_token(token, db)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get user's default organization
    from app.org.models import OrganizationMember
    member_result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user.id)
        .order_by(OrganizationMember.joined_at)
    )
    member = member_result.scalars().first()
    if not member:
        raise HTTPException(status_code=400, detail="User has no organization")
    org_id = member.organization_id

    # Generate key: mk_live_<base64url>
    raw_key = "mk_live_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = raw_key[:12]  # "mk_live_xxxx"
    key_prefix = raw_key[:12]

    from datetime import datetime, timedelta, UTC
    expires_at = None
    if api_key_request.expires_days:
        expires_at = datetime.now(UTC) + timedelta(days=api_key_request.expires_days)

    db_key = ApiKey(
        key_id=key_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=api_key_request.name,
        user_id=user.id,
        organization_id=org_id,
        expires_at=expires_at,
    )
    db.add(db_key)
    await db.commit()

    return ApiKeyCreated(key=raw_key, key_id=key_id, key_prefix=key_prefix)


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the authenticated user (without secrets)."""
    try:
        token = _extract_bearer_or_cookie_token(request)
        user = await _get_user_by_token(token, db)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        ApiKeyOut(
            id=k.id,
            key_id=k.key_id,
            key_prefix=k.key_prefix,
            name=k.name,
            organization_id=k.organization_id,
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            created_at=k.created_at.isoformat(),
        )
        for k in keys
    ]


@router.delete("/api-key/{key_id}")
async def delete_api_key(
    key_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Delete an API key."""
    try:
        token = _extract_bearer_or_cookie_token(request)
        user = await _get_user_by_token(token, db)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(
        select(ApiKey).where(ApiKey.key_id == key_id, ApiKey.user_id == user.id)
    )
    key = result.scalars().first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(key)
    await db.commit()
    return {"status": "deleted", "key_id": key_id}
