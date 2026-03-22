from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.satellite_image import SatelliteImage
from app.models.zone import Zone
from app.schemas.user import UserOut, UserCreate, UserUpdate
from app.services.auth_service import hash_password
from app.dependencies import require_role
from app.config import settings

router = APIRouter(tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "super_admin")),
):
    result = await db.execute(select(User))
    return result.scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "super_admin")),
):
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "super_admin")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/system/health")
async def system_health(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "super_admin")),
):
    last_image = await db.execute(
        select(SatelliteImage).order_by(SatelliteImage.ingested_at.desc()).limit(1)
    )
    last = last_image.scalar_one_or_none()

    return {
        "last_ingestion": last.ingested_at.isoformat() if last else None,
        "last_image_usable": last.is_usable if last else None,
        "imagery_provider": settings.imagery_provider,
    }


@router.get("/zones")
async def list_zones(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "super_admin")),
):
    result = await db.execute(select(Zone))
    return result.scalars().all()
