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

