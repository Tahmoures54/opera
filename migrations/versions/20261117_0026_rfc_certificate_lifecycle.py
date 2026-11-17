"""Promote legacy RF handover certificate records to explicit RFC certificates.

Revision ID: 20261117_0026
Revises: 20261117_0025
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0026"
down_revision = "20261117_0025"
branch_labels = None
depends_on = None


def upgrade():
    # Add explicit RFC fields and copy legacy RF values without discarding
    # the original columns. Keeping the old columns makes rollback/data audits safe.
    op.add_column(
        "commissioning_handover_package",
        sa.Column("rfc_certificate_number", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "commissioning_handover_package",
        sa.Column("rfc_certificate_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "commissioning_handover_package",
        sa.Column("rfc_issued_by_id", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE commissioning_handover_package "
        "SET rfc_certificate_number = rf_certificate_number, "
        "rfc_certificate_date = rf_certificate_date, "
        "rfc_issued_by_id = rf_issued_by_id"
    )

    # Drop the old two-character check before updating RF -> RFC.
    with op.batch_alter_table("commissioning_certificate", recreate="always") as batch:
        batch.drop_constraint("ck_comm_certificate_type", type_="check")
        batch.alter_column(
            "certificate_type",
            existing_type=sa.String(length=2),
            type_=sa.String(length=3),
            existing_nullable=False,
        )

    op.execute(
        "UPDATE commissioning_certificate SET certificate_type = 'RFC' "
        "WHERE certificate_type = 'RF'"
    )
    op.execute(
        "UPDATE commissioning_handover_package SET status = 'RFC_CERTIFIED' "
        "WHERE status = 'RF_CERTIFIED'"
    )
    op.execute(
        "UPDATE commissioning_handover_package SET status = 'RFC_PENDING' "
        "WHERE status = 'RF_PENDING'"
    )

    with op.batch_alter_table("commissioning_certificate", recreate="always") as batch:
        batch.create_check_constraint(
            "ck_comm_certificate_type",
            "certificate_type IN ('MC', 'RFC')",
        )


def downgrade():
    with op.batch_alter_table("commissioning_certificate", recreate="always") as batch:
        batch.drop_constraint("ck_comm_certificate_type", type_="check")

    op.execute(
        "UPDATE commissioning_certificate SET certificate_type = 'RF' "
        "WHERE certificate_type = 'RFC'"
    )
    op.execute(
        "UPDATE commissioning_handover_package SET status = 'RF_CERTIFIED' "
        "WHERE status = 'RFC_CERTIFIED'"
    )
    op.execute(
        "UPDATE commissioning_handover_package SET status = 'RF_PENDING' "
        "WHERE status = 'RFC_PENDING'"
    )

    with op.batch_alter_table("commissioning_certificate", recreate="always") as batch:
        batch.alter_column(
            "certificate_type",
            existing_type=sa.String(length=3),
            type_=sa.String(length=2),
            existing_nullable=False,
        )
        batch.create_check_constraint(
            "ck_comm_certificate_type",
            "certificate_type IN ('MC', 'RF')",
        )

    op.execute(
        "UPDATE commissioning_handover_package "
        "SET rf_certificate_number = rfc_certificate_number, "
        "rf_certificate_date = rfc_certificate_date, "
        "rf_issued_by_id = rfc_issued_by_id"
    )
    op.drop_column("commissioning_handover_package", "rfc_issued_by_id")
    op.drop_column("commissioning_handover_package", "rfc_certificate_date")
    op.drop_column("commissioning_handover_package", "rfc_certificate_number")
