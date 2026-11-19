"""Widen check sheet type column for mechanical test types (additive).

Revision ID: 20261119_0036
Revises: 20261118_0035

The enum is stored as a non-native string with no CHECK constraint, so new
values only need the column wide enough to hold them. Downgrade is a no-op:
narrowing the column could truncate values already stored.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_0036"
down_revision = "20261118_0035"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("commissioning_check_sheet") as batch:
        batch.alter_column(
            "sheet_type",
            existing_type=sa.String(length=15),
            type_=sa.String(length=30),
            existing_nullable=False,
        )


def downgrade():
    pass
