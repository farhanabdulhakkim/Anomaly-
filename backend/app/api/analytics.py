import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.api.auth import get_current_user
from app.repositories.repositories import AnalyticsRepository

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/fields/{field_id}/trend")
async def anomaly_trend(
    field_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns per-mission anomaly counts ordered by flight date.
    Use this to drive a time-series chart on the dashboard.
    """
    repo = AnalyticsRepository(db)
    rows = await repo.get_field_trend(field_id)
    return {
        "field_id": field_id,
        "trend": [
            {
                "mission_id": str(r["id"]),
                "mission_name": r["name"],
                "flight_date": r["flight_date"].isoformat() if r["flight_date"] else None,
                "anomaly_cells": r["anomaly_cells"],
                "total_anomaly_points": r["total_anomaly_points"],
                "reduction_pct": r["anomaly_reduction_pct"],
            }
            for r in rows
        ],
    }
