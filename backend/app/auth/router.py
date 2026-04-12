from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request, Response, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta

from app.core.database import get_db
from app.auth.models import User
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
    from app.org.models import Organization, OrganizationMember
    org_slug = f"user_{db_user.username}"
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
    await db.refresh(db_user)

    # Trigger async provisioning in background
    from app.org import provisioner
    background_tasks.add_task(provisioner.provision_org_schema, org_slug)

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
