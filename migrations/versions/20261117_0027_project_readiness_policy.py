"""Add project-scoped configurable commissioning readiness policy.

Revision ID: 20261117_0027
Revises: 20261117_0026
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0027"
down_revision = "20261117_0026"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "commissioning_project",
        sa.Column("readiness_policy_json", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("commissioning_project", "readiness_policy_json")
