"""Record witness/hold notification timestamps.

Revision ID: 20261117_0033
Revises: 20261117_0032
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0033"
down_revision = "20261117_0032"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "commissioning_witness_point",
        sa.Column("notified_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("commissioning_witness_point", "notified_at")
