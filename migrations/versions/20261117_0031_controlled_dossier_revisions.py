"""Add controlled subsystem dossier revisions and review history.

Revision ID: 20261117_0031
Revises: 20261117_0030
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0031"
down_revision = "20261117_0030"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commissioning_dossier_revision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("subsystem_id", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False, server_default="Subsystem Completion Dossier"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("issued_by_id", sa.Integer(), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("revision_number >= 1", name="ck_comm_dossier_revision_positive"),
        sa.CheckConstraint(
            "status IN ('DRAFT','IN_REVIEW','APPROVED','REJECTED','ISSUED')",
            name="ck_comm_dossier_revision_status",
        ),
        sa.CheckConstraint("length(snapshot_sha256) = 64", name="ck_comm_dossier_snapshot_sha256"),
        sa.ForeignKeyConstraint(
            ["project_id", "company_name"],
            ["commissioning_project.id", "commissioning_project.company_name"],
            name="fk_comm_dossier_revision_project_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["subsystem_id", "company_name"],
            ["commissioning_subsystem.id", "commissioning_subsystem.company_name"],
            name="fk_comm_dossier_revision_subsystem_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id", "company_name"],
            ["commissioning_dossier_revision.id", "commissioning_dossier_revision.company_name"],
            name="fk_comm_dossier_revision_supersedes_tenant",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_name", "project_id", "subsystem_id", "revision_number",
            name="uq_comm_dossier_revision_scope",
        ),
        sa.UniqueConstraint("id", "company_name", name="uq_comm_dossier_revision_id_company"),
    )
    op.create_index(
        "ix_comm_dossier_revision_scope_status",
        "commissioning_dossier_revision",
        ["company_name", "project_id", "subsystem_id", "status", "revision_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commissioning_dossier_revision_company_name"),
        "commissioning_dossier_revision", ["company_name"], unique=False,
    )
    op.create_table(
        "commissioning_dossier_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("dossier_revision_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("decision IN ('APPROVED','REJECTED')",
                           name="ck_comm_dossier_review_decision"),
        sa.ForeignKeyConstraint(
            ["dossier_revision_id", "company_name"],
            ["commissioning_dossier_revision.id", "commissioning_dossier_revision.company_name"],
            name="fk_comm_dossier_review_revision_tenant",
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_comm_dossier_review_revision_date",
        "commissioning_dossier_review",
        ["company_name", "dossier_revision_id", "decided_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commissioning_dossier_review_company_name"),
        "commissioning_dossier_review", ["company_name"], unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_commissioning_dossier_review_company_name"),
        table_name="commissioning_dossier_review",
    )
    op.drop_index("ix_comm_dossier_review_revision_date", table_name="commissioning_dossier_review")
    op.drop_table("commissioning_dossier_review")
    op.drop_index(
        op.f("ix_commissioning_dossier_revision_company_name"),
        table_name="commissioning_dossier_revision",
    )
    op.drop_index("ix_comm_dossier_revision_scope_status", table_name="commissioning_dossier_revision")
    op.drop_table("commissioning_dossier_revision")
