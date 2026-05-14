"""Initial schema with PostGIS

Revision ID: 0001
Revises:
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "fields",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("rice_type", sa.String(100)),
        sa.Column("soil_type", sa.String(100)),
        sa.Column("irrigation_type", sa.String(100)),
        sa.Column("area_hectares", sa.Float()),
        sa.Column("planting_date", sa.Date()),
        sa.Column("cell_size_m", sa.Integer(), default=10),
        sa.Column("boundary", geoalchemy2.Geometry("POLYGON", srid=4326), nullable=False),
        sa.Column("origin_lat", sa.Float()),
        sa.Column("origin_lon", sa.Float()),
        sa.Column("n_rows", sa.Integer()),
        sa.Column("n_cols", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_fields_boundary_gist", "fields", ["boundary"], postgresql_using="gist")
    op.create_index("ix_fields_owner_id", "fields", ["owner_id"])

    op.create_table(
        "grid_cells",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("field_id", UUID(as_uuid=True), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row", sa.Integer(), nullable=False),
        sa.Column("col", sa.Integer(), nullable=False),
        sa.Column("geom", geoalchemy2.Geometry("POLYGON", srid=4326), nullable=False),
        sa.Column("centre_lat", sa.Float(), nullable=False),
        sa.Column("centre_lon", sa.Float(), nullable=False),
        sa.Column("sw_lat", sa.Float(), nullable=False),
        sa.Column("sw_lon", sa.Float(), nullable=False),
        sa.Column("ne_lat", sa.Float(), nullable=False),
        sa.Column("ne_lon", sa.Float(), nullable=False),
        sa.UniqueConstraint("field_id", "row", "col", name="uq_grid_cell_field_row_col"),
    )
    op.create_index("ix_grid_cells_geom_gist", "grid_cells", ["geom"], postgresql_using="gist")
    op.create_index("ix_grid_cells_field_id", "grid_cells", ["field_id"])

    op.create_table(
        "missions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("field_id", UUID(as_uuid=True), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("drone_model", sa.String(100)),
        sa.Column("flight_altitude_m", sa.Float()),
        sa.Column("anomaly_mode", sa.String(20), default="rule_based"),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("flight_path", geoalchemy2.Geometry("LINESTRING", srid=4326)),
        sa.Column("total_points", sa.Integer(), default=0),
        sa.Column("anomaly_point_count", sa.Integer(), default=0),
        sa.Column("anomaly_cell_count", sa.Integer(), default=0),
        sa.Column("duration_s", sa.Float()),
        sa.Column("waypoints", sa.JSON()),
        sa.Column("flight_date", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_missions_flight_path_gist", "missions", ["flight_path"], postgresql_using="gist")
    op.create_index("ix_missions_field_id", "missions", ["field_id"])

    op.create_table(
        "telemetry_points",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("mission_id", UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326), nullable=False),
        sa.Column("altitude_m", sa.Float()),
        sa.Column("speed_ms", sa.Float()),
        sa.Column("roll_deg", sa.Float()),
        sa.Column("pitch_deg", sa.Float()),
        sa.Column("yaw_deg", sa.Float()),
        sa.Column("elapsed_s", sa.Float()),
        sa.Column("grid_row", sa.Integer()),
        sa.Column("grid_col", sa.Integer()),
        sa.Column("is_anomaly", sa.Boolean(), default=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_telemetry_geom_gist", "telemetry_points", ["geom"], postgresql_using="gist")
    op.create_index("ix_telemetry_mission_id", "telemetry_points", ["mission_id"])

    op.create_table(
        "anomalies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("mission_id", UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grid_cell_id", UUID(as_uuid=True), sa.ForeignKey("grid_cells.id", ondelete="CASCADE"), nullable=False),
        sa.Column("anomaly_count", sa.Integer(), default=0),
        sa.Column("total_points", sa.Integer(), default=0),
        sa.Column("density", sa.Float(), default=0.0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("mission_id", "grid_cell_id", name="uq_anomaly_mission_cell"),
    )
    op.create_index("ix_anomalies_mission_id", "anomalies", ["mission_id"])
    op.create_index("ix_anomalies_grid_cell_id", "anomalies", ["grid_cell_id"])

    op.create_table(
        "analytics_summary",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("mission_id", UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("total_cells", sa.Integer(), default=0),
        sa.Column("anomaly_cells", sa.Integer(), default=0),
        sa.Column("clean_cells", sa.Integer(), default=0),
        sa.Column("total_anomaly_points", sa.Integer(), default=0),
        sa.Column("avg_anomaly_density", sa.Float(), default=0.0),
        sa.Column("max_anomaly_density", sa.Float(), default=0.0),
        sa.Column("prev_mission_id", UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("anomaly_reduction_pct", sa.Float()),
        sa.Column("cell_change_count", sa.Integer()),
        sa.Column("hotspot_cell_ids", sa.JSON()),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("analytics_summary")
    op.drop_table("anomalies")
    op.drop_table("telemetry_points")
    op.drop_table("missions")
    op.drop_table("grid_cells")
    op.drop_table("fields")
    op.drop_table("users")
