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
    op.add_column(
        "commissioning_check_sheet_item",
        sa.Column("measurement_type", sa.String(length=20), nullable=False,
                  server_default=sa.text("'QUALITATIVE'")),
    )
    op.add_column(
        "commissioning_check_sheet_item",
        sa.Column("minimum_value", sa.Numeric(24, 8), nullable=True),
    )
    op.add_column(
        "commissioning_check_sheet_item",
        sa.Column("maximum_value", sa.Numeric(24, 8), nullable=True),
    )
    op.add_column(
        "commissioning_check_sheet_item",
        sa.Column("measured_value", sa.Numeric(24, 8), nullable=True),
    )

    if op.get_bind().dialect.name == "sqlite":
        # SQLite cannot add table CHECK constraints with ALTER TABLE. Triggers
        # enforce the same invariants without rebuilding a referenced table.
        for event in ("INSERT", "UPDATE"):
            trigger = f"trg_comm_check_measurement_{event.lower()}"
            op.execute(sa.text(f"""
                CREATE TRIGGER {trigger}
                BEFORE {event} ON commissioning_check_sheet_item
                WHEN
                    NEW.measurement_type NOT IN ('QUALITATIVE', 'NUMERIC')
                    OR (
                        NEW.minimum_value IS NOT NULL
                        AND NEW.maximum_value IS NOT NULL
                        AND NEW.minimum_value > NEW.maximum_value
                    )
                    OR (
                        NEW.measurement_type = 'NUMERIC'
                        AND (NEW.unit IS NULL OR length(trim(NEW.unit)) = 0)
                    )
                    OR (
                        NEW.measurement_type = 'QUALITATIVE'
                        AND (
                            NEW.minimum_value IS NOT NULL
                            OR NEW.maximum_value IS NOT NULL
                            OR NEW.measured_value IS NOT NULL
                        )
                    )
                BEGIN
                    SELECT RAISE(ABORT, 'invalid Check Sheet measurement configuration');
                END;
            """))
    else:
        op.create_check_constraint(
            "ck_comm_check_item_measurement_type",
            "commissioning_check_sheet_item",
            "measurement_type IN ('QUALITATIVE','NUMERIC')",
        )
        op.create_check_constraint(
            "ck_comm_check_item_measurement_range",
            "commissioning_check_sheet_item",
            "minimum_value IS NULL OR maximum_value IS NULL OR minimum_value <= maximum_value",
        )
        op.create_check_constraint(
            "ck_comm_check_item_numeric_unit",
            "commissioning_check_sheet_item",
            "measurement_type = 'QUALITATIVE' OR (unit IS NOT NULL AND length(trim(unit)) > 0)",
        )
        op.create_check_constraint(
            "ck_comm_check_item_qualitative_values",
            "commissioning_check_sheet_item",
            "measurement_type = 'NUMERIC' OR (minimum_value IS NULL AND maximum_value IS NULL AND measured_value IS NULL)",
        )


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_comm_check_measurement_insert"))
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_comm_check_measurement_update"))
    else:
        op.drop_constraint(
            "ck_comm_check_item_qualitative_values",
            "commissioning_check_sheet_item",
            type_="check",
        )
        op.drop_constraint(
            "ck_comm_check_item_numeric_unit",
            "commissioning_check_sheet_item",
            type_="check",
        )
        op.drop_constraint(
            "ck_comm_check_item_measurement_range",
            "commissioning_check_sheet_item",
            type_="check",
        )
        op.drop_constraint(
            "ck_comm_check_item_measurement_type",
            "commissioning_check_sheet_item",
            type_="check",
        )
    op.drop_column("commissioning_check_sheet_item", "measured_value")
    op.drop_column("commissioning_check_sheet_item", "maximum_value")
    op.drop_column("commissioning_check_sheet_item", "minimum_value")
    op.drop_column("commissioning_check_sheet_item", "measurement_type")
