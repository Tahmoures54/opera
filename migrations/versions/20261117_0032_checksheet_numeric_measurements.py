"""Add numeric measurement capture to commissioning Check Sheets.

Revision ID: 20261117_0032
Revises: 20261117_0031
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0032"
down_revision = "20261117_0031"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("commissioning_check_sheet_item") as batch:
        batch.add_column(sa.Column("measurement_type", sa.String(length=20), nullable=False, server_default="QUALITATIVE"))
        batch.add_column(sa.Column("minimum_value", sa.Numeric(24, 8), nullable=True))
        batch.add_column(sa.Column("maximum_value", sa.Numeric(24, 8), nullable=True))
        batch.add_column(sa.Column("measured_value", sa.Numeric(24, 8), nullable=True))
        batch.create_check_constraint(
            "ck_comm_check_item_measurement_type",
            "measurement_type IN ('QUALITATIVE','NUMERIC')",
        )
        batch.create_check_constraint(
            "ck_comm_check_item_measurement_range",
            "minimum_value IS NULL OR maximum_value IS NULL OR minimum_value <= maximum_value",
        )


def downgrade():
    with op.batch_alter_table("commissioning_check_sheet_item") as batch:
        batch.drop_constraint("ck_comm_check_item_measurement_range", type_="check")
        batch.drop_constraint("ck_comm_check_item_measurement_type", type_="check")
        batch.drop_column("measured_value")
        batch.drop_column("maximum_value")
        batch.drop_column("minimum_value")
        batch.drop_column("measurement_type")
