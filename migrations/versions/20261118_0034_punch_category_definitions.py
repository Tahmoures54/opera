"""Add project-defined Punch category table and item category code (additive).

Revision ID: 20261118_0034
Revises: 20261117_0033

Additive only. Existing reads and writes keep using the PunchCategory enum.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261118_0034"
down_revision = "20261117_0033"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commissioning_punch_category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id", "company_name"],
            ["commissioning_project.id", "commissioning_project.company_name"],
            name="fk_comm_punch_category_project_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "code", name="uq_comm_punch_category_project_code"),
    )
    op.create_index(
        op.f("ix_commissioning_punch_category_company_name"),
        "commissioning_punch_category", ["company_name"], unique=False,
    )
    op.create_index(
        "ix_comm_punch_category_company_project",
        "commissioning_punch_category", ["company_name", "project_id"], unique=False,
    )
    op.add_column(
        "commissioning_punch_item",
        sa.Column("category_code", sa.String(length=8), nullable=True),
    )


def downgrade():
    op.drop_column("commissioning_punch_item", "category_code")
    op.drop_index("ix_comm_punch_category_company_project", table_name="commissioning_punch_category")
    op.drop_index(op.f("ix_commissioning_punch_category_company_name"), table_name="commissioning_punch_category")
    op.drop_table("commissioning_punch_category")
