import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.api.auth import get_current_user
from app.services.field_service import FieldService
from app.schemas.schemas import FieldCreate, FieldUpdate, FieldOut

router = APIRouter(prefix="/api/fields", tags=["fields"])


@router.post("", response_model=FieldOut, status_code=201)
async def create_field(
    data: FieldCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = FieldService(db)
    return await svc.create_field(current_user.id, data)


@router.get("", response_model=list[FieldOut])
async def list_fields(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = FieldService(db)
    return await svc.list_fields(current_user.id)


@router.get("/{field_id}", response_model=FieldOut)
async def get_field(
    field_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = FieldService(db)
    field = await svc.get_field(field_id)
    if field.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return field


@router.patch("/{field_id}", response_model=FieldOut)
async def update_field(
    field_id: uuid.UUID,
    data: FieldUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = FieldService(db)
    field = await svc.get_field(field_id)
    if field.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return await svc.update_field(field_id, data)


@router.get("/{field_id}/grid/geojson")
async def get_grid_geojson(
    field_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = FieldService(db)
    return await svc.get_grid_geojson(field_id)
