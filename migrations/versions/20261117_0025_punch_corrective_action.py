"""Add corrective action evidence to Punch List items.

Revision ID: 20261117_0025
Revises: 20261117_0024
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0025"
down_revision = "20261117_0024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "commissioning_punch_item",
        sa.Column("corrective_action", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("commissioning_punch_item", "corrective_action")
