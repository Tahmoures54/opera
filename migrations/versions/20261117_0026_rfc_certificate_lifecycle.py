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
    # Preserve all previously issued certificate references while making the
    # domain code unambiguous. Package columns are renamed, not discarded.
    with op.batch_alter_table("commissioning_handover_package") as batch:
        batch.alter_column(
            "rf_certificate_number",
            new_column_name="rfc_certificate_number",
            existing_type=sa.String(length=100),
            existing_nullable=True,
        )
        batch.alter_column(
            "rf_certificate_date",
            new_column_name="rfc_certificate_date",
            existing_type=sa.Date(),
            existing_nullable=True,
        )
        batch.alter_column(
            "rf_issued_by_id",
            new_column_name="rfc_issued_by_id",
            existing_type=sa.Integer(),
            existing_nullable=True,
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

    with op.batch_alter_table("commissioning_handover_package") as batch:
        batch.alter_column(
            "rfc_certificate_number",
            new_column_name="rf_certificate_number",
            existing_type=sa.String(length=100),
            existing_nullable=True,
        )
        batch.alter_column(
            "rfc_certificate_date",
            new_column_name="rf_certificate_date",
            existing_type=sa.Date(),
            existing_nullable=True,
        )
        batch.alter_column(
            "rfc_issued_by_id",
            new_column_name="rf_issued_by_id",
            existing_type=sa.Integer(),
            existing_nullable=True,
        )
