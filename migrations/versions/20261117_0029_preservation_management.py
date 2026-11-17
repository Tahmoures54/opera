"""Add equipment preservation plans and immutable inspection history.

Revision ID: 20261117_0029
Revises: 20261117_0028
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0029"
down_revision = "20261117_0028"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commissioning_preservation_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=False),
        sa.Column("plan_number", sa.String(length=80), nullable=False),
        sa.Column("activity", sa.String(length=200), nullable=False),
        sa.Column("procedure_reference", sa.String(length=150), nullable=False),
        sa.Column("procedure_revision", sa.String(length=50), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("last_performed_at", sa.Date(), nullable=True),
        sa.Column("responsible_company", sa.String(length=150), nullable=True),
        sa.Column("assigned_to_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ACTIVE"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "interval_days > 0",
            name="ck_comm_preservation_interval",
        ),
        sa.CheckConstraint(
            "length(trim(plan_number)) > 0",
            name="ck_comm_preservation_plan_number",
        ),
        sa.CheckConstraint(
            "length(trim(procedure_reference)) > 0",
            name="ck_comm_preservation_procedure_reference",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','ACTION_REQUIRED','SUSPENDED','CLOSED')",
            name="ck_comm_preservation_status",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "company_name"],
            ["commissioning_project.id", "commissioning_project.company_name"],
            name="fk_comm_preservation_plan_project_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id", "company_name"],
            ["commissioning_equipment.id", "commissioning_equipment.company_name"],
            name="fk_comm_preservation_plan_equipment_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["commissioning_project.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"], ["commissioning_equipment.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_id"], ["user.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_name", "project_id", "plan_number",
                            name="uq_comm_preservation_plan_number"),
        sa.UniqueConstraint("id", "company_name",
                            name="uq_comm_preservation_plan_id_company"),
    )
    op.create_index(
        "ix_comm_preservation_due",
        "commissioning_preservation_plan",
        ["company_name", "project_id", "status", "next_due_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commissioning_preservation_plan_company_name"),
        "commissioning_preservation_plan", ["company_name"], unique=False,
    )

    op.create_table(
        "commissioning_preservation_inspection",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("performed_at", sa.Date(), nullable=False),
        sa.Column("result", sa.String(length=30), nullable=False),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("environmental_conditions", sa.Text(), nullable=True),
        sa.Column("corrective_action", sa.Text(), nullable=True),
        sa.Column("procedure_reference_snapshot", sa.String(length=150), nullable=False),
        sa.Column("procedure_revision_snapshot", sa.String(length=50), nullable=False),
        sa.Column("interval_days_snapshot", sa.Integer(), nullable=False),
        sa.Column("next_due_date_after", sa.Date(), nullable=True),
        sa.Column("performed_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "result IN ('COMPLIANT','NON_COMPLIANT','NOT_APPLICABLE')",
            name="ck_comm_preservation_inspection_result",
        ),
        sa.CheckConstraint(
            "interval_days_snapshot > 0",
            name="ck_comm_preservation_inspection_interval",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "company_name"],
            ["commissioning_project.id", "commissioning_project.company_name"],
            name="fk_comm_preservation_inspection_project_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id", "company_name"],
            ["commissioning_preservation_plan.id", "commissioning_preservation_plan.company_name"],
            name="fk_comm_preservation_inspection_plan_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["commissioning_project.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["commissioning_preservation_plan.id"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_id"], ["user.id"], ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "company_name",
                            name="uq_comm_preservation_inspection_id_company"),
    )
    op.create_index(
        "ix_comm_preservation_inspection_plan_date",
        "commissioning_preservation_inspection",
        ["company_name", "plan_id", "performed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commissioning_preservation_inspection_company_name"),
        "commissioning_preservation_inspection", ["company_name"], unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_commissioning_preservation_inspection_company_name"),
        table_name="commissioning_preservation_inspection",
    )
    op.drop_index(
        "ix_comm_preservation_inspection_plan_date",
        table_name="commissioning_preservation_inspection",
    )
    op.drop_table("commissioning_preservation_inspection")
    op.drop_index(
        op.f("ix_commissioning_preservation_plan_company_name"),
        table_name="commissioning_preservation_plan",
    )
    op.drop_index(
        "ix_comm_preservation_due",
        table_name="commissioning_preservation_plan",
    )
    op.drop_table("commissioning_preservation_plan")
