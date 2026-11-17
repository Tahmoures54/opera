"""Add immutable MC/RF completion certificates.

Revision ID: 20261117_0024
Revises: 20261117_0023
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0024"
down_revision = "20261117_0023"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_comm_handover_id_company", "commissioning_handover_package",
        ["id", "company_name"],
    )
    op.create_table(
        "commissioning_certificate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("subsystem_id", sa.Integer(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("certificate_type", sa.String(length=2), nullable=False),
        sa.Column("certificate_number", sa.String(length=100), nullable=False),
        sa.Column("certificate_date", sa.Date(), nullable=False),
        sa.Column("issued_by_id", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("certificate_type IN ('MC', 'RF')",
                           name="ck_comm_certificate_type"),
        sa.ForeignKeyConstraint(["company_name"], ["commissioning_project.company_name"],
                                name="fk_comm_certificate_company"),
        sa.ForeignKeyConstraint(["issued_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["package_id", "company_name"],
                                ["commissioning_handover_package.id", "commissioning_handover_package.company_name"],
                                name="fk_comm_certificate_package_tenant"),
        sa.ForeignKeyConstraint(["project_id", "company_name"],
                                ["commissioning_project.id", "commissioning_project.company_name"],
                                name="fk_comm_certificate_project_tenant"),
        sa.ForeignKeyConstraint(["subsystem_id", "company_name"],
                                ["commissioning_subsystem.id", "commissioning_subsystem.company_name"],
                                name="fk_comm_certificate_subsystem_tenant"),
        sa.ForeignKeyConstraint(["package_id"], ["commissioning_handover_package.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["commissioning_project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subsystem_id"], ["commissioning_subsystem.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_name", "certificate_number",
                            name="uq_comm_certificate_company_number"),
        sa.UniqueConstraint("company_name", "package_id", "certificate_type",
                            name="uq_comm_certificate_package_type"),
    )
    op.create_index("ix_comm_certificate_company_project_date",
                    "commissioning_certificate",
                    ["company_name", "project_id", "certificate_date"], unique=False)
    op.create_index(op.f("ix_commissioning_certificate_company_name"),
                    "commissioning_certificate", ["company_name"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_commissioning_certificate_company_name"),
                  table_name="commissioning_certificate")
    op.drop_index("ix_comm_certificate_company_project_date",
                  table_name="commissioning_certificate")
    op.drop_table("commissioning_certificate")
    op.drop_constraint("uq_comm_handover_id_company",
                       "commissioning_handover_package", type_="unique")
