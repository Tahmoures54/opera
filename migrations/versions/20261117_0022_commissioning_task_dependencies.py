"""Add finish-to-start commissioning task dependencies.

Revision ID: 20261117_0022
Revises: 20261117_0021
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0022"
down_revision = "20261117_0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commissioning_task_dependency",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("predecessor_task_id", sa.Integer(), nullable=False),
        sa.Column("successor_task_id", sa.Integer(), nullable=False),
        sa.Column("dependency_type", sa.String(length=20), nullable=False),
        sa.Column("lag_days", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("predecessor_task_id != successor_task_id",
                           name="ck_comm_task_dependency_not_self"),
        sa.CheckConstraint("lag_days >= 0",
                           name="ck_comm_task_dependency_lag_nonnegative"),
        sa.ForeignKeyConstraint(["company_name"], ["commissioning_project.company_name"],
                                name="fk_comm_task_dependency_company"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["predecessor_task_id", "company_name"],
                                ["commissioning_task.id", "commissioning_task.company_name"],
                                name="fk_comm_task_dependency_predecessor_tenant"),
        sa.ForeignKeyConstraint(["project_id", "company_name"],
                                ["commissioning_project.id", "commissioning_project.company_name"],
                                name="fk_comm_task_dependency_project_tenant"),
        sa.ForeignKeyConstraint(["successor_task_id", "company_name"],
                                ["commissioning_task.id", "commissioning_task.company_name"],
                                name="fk_comm_task_dependency_successor_tenant"),
        sa.ForeignKeyConstraint(["project_id"], ["commissioning_project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["predecessor_task_id"], ["commissioning_task.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["successor_task_id"], ["commissioning_task.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_name", "predecessor_task_id", "successor_task_id",
                            name="uq_comm_task_dependency_pair"),
    )
    op.create_index(
        "ix_comm_task_dependency_project_successor",
        "commissioning_task_dependency",
        ["company_name", "project_id", "successor_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commissioning_task_dependency_company_name"),
        "commissioning_task_dependency", ["company_name"], unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_commissioning_task_dependency_company_name"),
                  table_name="commissioning_task_dependency")
    op.drop_index("ix_comm_task_dependency_project_successor",
                  table_name="commissioning_task_dependency")
    op.drop_table("commissioning_task_dependency")
