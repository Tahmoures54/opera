"""Add energy isolation register for subsystem work (additive).

Revision ID: 20261119_0037
Revises: 20261119_0036
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_0037"
down_revision = "20261119_0036"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commissioning_isolation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("subsystem_id", sa.Integer(), nullable=False),
        sa.Column("tag_ref", sa.String(length=100), nullable=False),
        sa.Column("energy_type", sa.String(length=30), nullable=False),
        sa.Column("purpose", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("applied_by_id", sa.Integer(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.Column("released_by_id", sa.Integer(), nullable=True),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('APPLIED','RELEASED')", name="ck_comm_isolation_status"),
        sa.CheckConstraint("length(trim(tag_ref)) > 0", name="ck_comm_isolation_tag"),
        sa.ForeignKeyConstraint(
            ["project_id", "company_name"],
            ["commissioning_project.id", "commissioning_project.company_name"],
            name="fk_comm_isolation_project_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["subsystem_id", "company_name"],
            ["commissioning_subsystem.id", "commissioning_subsystem.company_name"],
            name="fk_comm_isolation_subsystem_tenant",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["commissioning_project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subsystem_id"], ["commissioning_subsystem.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["applied_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["released_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_commissioning_isolation_company_name"),
        "commissioning_isolation", ["company_name"], unique=False,
    )
    op.create_index(
        "ix_comm_isolation_company_subsystem_status",
        "commissioning_isolation", ["company_name", "subsystem_id", "status"], unique=False,
    )


def downgrade():
    op.drop_index("ix_comm_isolation_company_subsystem_status", table_name="commissioning_isolation")
    op.drop_index(op.f("ix_commissioning_isolation_company_name"), table_name="commissioning_isolation")
    op.drop_table("commissioning_isolation")
