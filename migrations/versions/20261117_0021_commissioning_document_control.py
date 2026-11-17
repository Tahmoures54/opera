"""Add controlled commissioning document register and review history.

Revision ID: 20261117_0021
Revises: 20261117_0020
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0021"
down_revision = "20261117_0020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commissioning_document",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("system_id", sa.Integer(), nullable=True),
        sa.Column("subsystem_id", sa.Integer(), nullable=True),
        sa.Column("equipment_id", sa.Integer(), nullable=True),
        sa.Column("document_number", sa.String(length=120), nullable=False),
        sa.Column("revision", sa.String(length=20), nullable=False),
        sa.Column("revision_sequence", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("document_type", sa.String(length=80), nullable=False),
        sa.Column("discipline", sa.String(length=80), nullable=False),
        sa.Column("purpose", sa.String(length=80), nullable=True),
        sa.Column("status", sa.Enum("DRAFT", "IN_REVIEW", "APPROVED", "REJECTED", "SUPERSEDED",
                                   name="commissioning_document_status", native_enum=False), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("revision_sequence >= 1", name="ck_comm_document_revision_sequence"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["equipment_id", "company_name"],
                                ["commissioning_equipment.id", "commissioning_equipment.company_name"],
                                name="fk_comm_document_equipment_tenant"),
        sa.ForeignKeyConstraint(["equipment_id"], ["commissioning_equipment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "company_name"],
                                ["commissioning_project.id", "commissioning_project.company_name"],
                                name="fk_comm_document_project_tenant"),
        sa.ForeignKeyConstraint(["project_id"], ["commissioning_project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subsystem_id", "company_name"],
                                ["commissioning_subsystem.id", "commissioning_subsystem.company_name"],
                                name="fk_comm_document_subsystem_tenant"),
        sa.ForeignKeyConstraint(["subsystem_id"], ["commissioning_subsystem.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["system_id", "company_name"],
                                ["commissioning_system.id", "commissioning_system.company_name"],
                                name="fk_comm_document_system_tenant"),
        sa.ForeignKeyConstraint(["system_id"], ["commissioning_system.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id", "company_name"],
                                ["commissioning_document.id", "commissioning_document.company_name"],
                                name="fk_comm_document_supersedes_tenant"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["commissioning_document.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_name", "project_id", "document_number", "revision_sequence",
                            name="uq_comm_document_revision_sequence"),
        sa.UniqueConstraint("company_name", "project_id", "document_number", "revision",
                            name="uq_comm_document_revision"),
        sa.UniqueConstraint("id", "company_name", name="uq_comm_document_id_company"),
    )
    op.create_index("ix_comm_document_company_project_status", "commissioning_document",
                    ["company_name", "project_id", "status"], unique=False)
    op.create_index("ix_comm_document_company_number", "commissioning_document",
                    ["company_name", "document_number"], unique=False)
    op.create_index(op.f("ix_commissioning_document_company_name"), "commissioning_document",
                    ["company_name"], unique=False)

    op.create_table(
        "commissioning_document_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id", "company_name"],
                                ["commissioning_document.id", "commissioning_document.company_name"],
                                name="fk_comm_document_review_document_tenant"),
        sa.ForeignKeyConstraint(["document_id"], ["commissioning_document.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comm_document_review_company_document", "commissioning_document_review",
                    ["company_name", "document_id"], unique=False)
    op.create_index(op.f("ix_commissioning_document_review_company_name"),
                    "commissioning_document_review", ["company_name"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_commissioning_document_review_company_name"),
                  table_name="commissioning_document_review")
    op.drop_index("ix_comm_document_review_company_document", table_name="commissioning_document_review")
    op.drop_table("commissioning_document_review")
    op.drop_index(op.f("ix_commissioning_document_company_name"), table_name="commissioning_document")
    op.drop_index("ix_comm_document_company_number", table_name="commissioning_document")
    op.drop_index("ix_comm_document_company_project_status", table_name="commissioning_document")
    op.drop_table("commissioning_document")
