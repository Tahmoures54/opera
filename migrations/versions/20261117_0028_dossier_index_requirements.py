"""Add project-scoped configurable subsystem dossier index requirements.

Revision ID: 20261117_0028
Revises: 20261117_0027
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0028"
down_revision = "20261117_0027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commissioning_dossier_requirement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=80), nullable=False),
        sa.Column("discipline", sa.String(length=80), nullable=False, server_default="ANY"),
        sa.Column("minimum_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("require_approved", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_evidence", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "minimum_count >= 1 AND minimum_count <= 1000",
            name="ck_comm_dossier_requirement_minimum",
        ),
        sa.CheckConstraint(
            "length(trim(document_type)) > 0",
            name="ck_comm_dossier_requirement_type",
        ),
        sa.CheckConstraint(
            "length(trim(discipline)) > 0",
            name="ck_comm_dossier_requirement_discipline",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "company_name"],
            ["commissioning_project.id", "commissioning_project.company_name"],
            name="fk_comm_dossier_requirement_project_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["commissioning_project.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_name", "project_id", "document_type", "discipline",
            name="uq_comm_dossier_requirement_scope",
        ),
    )
    op.create_index(
        "ix_comm_dossier_requirement_project_active",
        "commissioning_dossier_requirement",
        ["company_name", "project_id", "is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commissioning_dossier_requirement_company_name"),
        "commissioning_dossier_requirement",
        ["company_name"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_commissioning_dossier_requirement_company_name"),
        table_name="commissioning_dossier_requirement",
    )
    op.drop_index(
        "ix_comm_dossier_requirement_project_active",
        table_name="commissioning_dossier_requirement",
    )
    op.drop_table("commissioning_dossier_requirement")
