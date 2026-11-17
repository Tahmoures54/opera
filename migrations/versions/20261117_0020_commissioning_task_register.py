"""Add the project-scoped commissioning task register.

Revision ID: 20261117_0020
Revises: 20261117_0019
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0020"
down_revision = "20261117_0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commissioning_task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("system_id", sa.Integer(), nullable=False),
        sa.Column("subsystem_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=True),
        sa.Column("task_number", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("activity_type", sa.Enum("CCK", "STS", "PIP", "PRC", "FTS", "OTS", "PVP", name="commissioning_task_type", native_enum=False), nullable=False),
        sa.Column("discipline", sa.String(length=80), nullable=False),
        sa.Column("progress_stage", sa.String(length=80), nullable=True),
        sa.Column("progress_substage", sa.String(length=80), nullable=True),
        sa.Column("assigned_group", sa.String(length=120), nullable=True),
        sa.Column("estimated_man_hours", sa.Float(), nullable=False),
        sa.Column("spent_man_hours", sa.Float(), nullable=False),
        sa.Column("planned_start_date", sa.Date(), nullable=True),
        sa.Column("planned_finish_date", sa.Date(), nullable=True),
        sa.Column("actual_start_date", sa.Date(), nullable=True),
        sa.Column("actual_finish_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Enum("NOT_STARTED", "READY", "IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED", name="commissioning_task_status", native_enum=False), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("estimated_man_hours >= 0", name="ck_comm_task_estimated_hours_nonnegative"),
        sa.CheckConstraint("spent_man_hours >= 0", name="ck_comm_task_spent_hours_nonnegative"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["equipment_id", "company_name"], ["commissioning_equipment.id", "commissioning_equipment.company_name"], name="fk_comm_task_equipment_tenant"),
        sa.ForeignKeyConstraint(["equipment_id"], ["commissioning_equipment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "company_name"], ["commissioning_project.id", "commissioning_project.company_name"], name="fk_comm_task_project_tenant"),
        sa.ForeignKeyConstraint(["project_id"], ["commissioning_project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subsystem_id", "company_name"], ["commissioning_subsystem.id", "commissioning_subsystem.company_name"], name="fk_comm_task_subsystem_tenant"),
        sa.ForeignKeyConstraint(["subsystem_id"], ["commissioning_subsystem.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["system_id", "company_name"], ["commissioning_system.id", "commissioning_system.company_name"], name="fk_comm_task_system_tenant"),
        sa.ForeignKeyConstraint(["system_id"], ["commissioning_system.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_name", "task_number", name="uq_comm_task_number"),
        sa.UniqueConstraint("id", "company_name", name="uq_comm_task_id_company"),
    )
    op.create_index("ix_comm_task_company_project_status", "commissioning_task", ["company_name", "project_id", "status"], unique=False)
    op.create_index("ix_comm_task_company_subsystem_type", "commissioning_task", ["company_name", "subsystem_id", "activity_type"], unique=False)
    op.create_index(op.f("ix_commissioning_task_company_name"), "commissioning_task", ["company_name"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_commissioning_task_company_name"), table_name="commissioning_task")
    op.drop_index("ix_comm_task_company_subsystem_type", table_name="commissioning_task")
    op.drop_index("ix_comm_task_company_project_status", table_name="commissioning_task")
    op.drop_table("commissioning_task")
