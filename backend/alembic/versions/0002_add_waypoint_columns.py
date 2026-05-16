"""Add waypoint_filename and waypoint_raw to missions

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("missions", sa.Column("waypoint_filename", sa.String(255), nullable=True))
    op.add_column("missions", sa.Column("waypoint_raw", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("missions", "waypoint_raw")
    op.drop_column("missions", "waypoint_filename")
