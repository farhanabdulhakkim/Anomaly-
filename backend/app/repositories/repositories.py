import uuid
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.field import Field
from app.models.grid_cell import GridCell
from app.models.mission import Mission
from app.models.anomaly import Anomaly
from app.models.analytics import AnalyticsSummary


# ── User Repository ───────────────────────────────────────────────────────────

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user


# ── Field Repository ──────────────────────────────────────────────────────────

class FieldRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, field: Field) -> Field:
        self.db.add(field)
        await self.db.commit()
        await self.db.refresh(field)
        return field

    async def get_by_id(self, field_id: uuid.UUID) -> Optional[Field]:
        result = await self.db.execute(select(Field).where(Field.id == field_id))
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner_id: uuid.UUID) -> List[Field]:
        result = await self.db.execute(select(Field).where(Field.owner_id == owner_id))
        return result.scalars().all()

    async def update(self, field: Field) -> Field:
        await self.db.commit()
        await self.db.refresh(field)
        return field

    async def get_grid_cells(self, field_id: uuid.UUID) -> List[GridCell]:
        result = await self.db.execute(
            select(GridCell).where(GridCell.field_id == field_id).order_by(GridCell.row, GridCell.col)
        )
        return result.scalars().all()

    async def bulk_insert_grid_cells(self, cells: List[GridCell]) -> None:
        self.db.add_all(cells)
        await self.db.commit()


# ── Mission Repository ────────────────────────────────────────────────────────

class MissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, mission: Mission) -> Mission:
        self.db.add(mission)
        await self.db.commit()
        await self.db.refresh(mission)
        return mission

    async def get_by_id(self, mission_id: uuid.UUID) -> Optional[Mission]:
        result = await self.db.execute(select(Mission).where(Mission.id == mission_id))
        return result.scalar_one_or_none()

    async def list_by_field(self, field_id: uuid.UUID) -> List[Mission]:
        result = await self.db.execute(
            select(Mission).where(Mission.field_id == field_id).order_by(Mission.created_at.desc())
        )
        return result.scalars().all()

    async def get_previous_mission(self, field_id: uuid.UUID, before_mission_id: uuid.UUID) -> Optional[Mission]:
        """Return the most recent completed mission before the given one."""
        current = await self.get_by_id(before_mission_id)
        result = await self.db.execute(
            select(Mission)
            .where(
                Mission.field_id == field_id,
                Mission.status == "completed",
                Mission.created_at < current.created_at,
            )
            .order_by(Mission.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update(self, mission: Mission) -> Mission:
        await self.db.commit()
        await self.db.refresh(mission)
        return mission

    async def bulk_insert_anomalies(self, anomalies: List[Anomaly]) -> None:
        self.db.add_all(anomalies)
        await self.db.commit()

    async def get_anomalies(self, mission_id: uuid.UUID) -> List[Anomaly]:
        result = await self.db.execute(
            select(Anomaly)
            .where(Anomaly.mission_id == mission_id, Anomaly.anomaly_count > 0)
            .options(selectinload(Anomaly.grid_cell))
            .order_by(Anomaly.anomaly_count.desc())
        )
        return result.scalars().all()


# ── Analytics Repository ──────────────────────────────────────────────────────

class AnalyticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(self, summary: AnalyticsSummary) -> AnalyticsSummary:
        self.db.add(summary)
        await self.db.commit()
        await self.db.refresh(summary)
        return summary

    async def get_by_mission(self, mission_id: uuid.UUID) -> Optional[AnalyticsSummary]:
        result = await self.db.execute(
            select(AnalyticsSummary).where(AnalyticsSummary.mission_id == mission_id)
        )
        return result.scalar_one_or_none()

    async def get_field_trend(self, field_id: uuid.UUID) -> List[dict]:
        """Return anomaly_cells per mission ordered by date for trend charts."""
        result = await self.db.execute(
            select(
                Mission.id,
                Mission.name,
                Mission.flight_date,
                AnalyticsSummary.anomaly_cells,
                AnalyticsSummary.total_anomaly_points,
                AnalyticsSummary.anomaly_reduction_pct,
            )
            .join(AnalyticsSummary, AnalyticsSummary.mission_id == Mission.id)
            .where(Mission.field_id == field_id, Mission.status == "completed")
            .order_by(Mission.flight_date.asc())
        )
        return [row._asdict() for row in result.all()]
