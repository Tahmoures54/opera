"""Add task execution metrics to progress snapshots.

Revision ID: 20261117_0023
Revises: 20261117_0022
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0023"
down_revision = "20261117_0022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("commissioning_progress_snapshot",
                  sa.Column("task_total", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("commissioning_progress_snapshot",
                  sa.Column("task_completed", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("commissioning_progress_snapshot",
                  sa.Column("task_percent_complete", sa.Float(), nullable=False, server_default=sa.text("0")))
    op.add_column("commissioning_progress_snapshot",
                  sa.Column("task_weighted_percent", sa.Float(), nullable=False, server_default=sa.text("0")))
    op.add_column("commissioning_progress_snapshot",
                  sa.Column("task_estimated_hours", sa.Float(), nullable=False, server_default=sa.text("0")))
    op.add_column("commissioning_progress_snapshot",
                  sa.Column("task_completed_hours", sa.Float(), nullable=False, server_default=sa.text("0")))
    op.create_check_constraint(
        "ck_comm_progress_task_percent_range", "commissioning_progress_snapshot",
        "task_percent_complete >= 0 AND task_percent_complete <= 100",
    )
    op.create_check_constraint(
        "ck_comm_progress_task_weighted_range", "commissioning_progress_snapshot",
        "task_weighted_percent >= 0 AND task_weighted_percent <= 100",
    )
    op.create_check_constraint(
        "ck_comm_progress_task_hours_nonnegative", "commissioning_progress_snapshot",
        "task_estimated_hours >= 0 AND task_completed_hours >= 0",
    )


def downgrade():
    op.drop_constraint("ck_comm_progress_task_hours_nonnegative",
                       "commissioning_progress_snapshot", type_="check")
    op.drop_constraint("ck_comm_progress_task_weighted_range",
                       "commissioning_progress_snapshot", type_="check")
    op.drop_constraint("ck_comm_progress_task_percent_range",
                       "commissioning_progress_snapshot", type_="check")
    op.drop_column("commissioning_progress_snapshot", "task_completed_hours")
    op.drop_column("commissioning_progress_snapshot", "task_estimated_hours")
    op.drop_column("commissioning_progress_snapshot", "task_weighted_percent")
    op.drop_column("commissioning_progress_snapshot", "task_percent_complete")
    op.drop_column("commissioning_progress_snapshot", "task_completed")
    op.drop_column("commissioning_progress_snapshot", "task_total")
