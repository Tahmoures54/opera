"""Backfill default Punch category definitions and item category codes (P2).

Revision ID: 20261118_0035
Revises: 20261118_0034

Idempotent: definitions are inserted only where a project lacks the code, and
item codes are set only where they are still NULL. Existing enum values are
never changed. Downgrade only clears item category codes; it does not delete
definitions, because projects may have edited them.
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "20261118_0035"
down_revision = "20261118_0034"
branch_labels = None
depends_on = None

DEFAULT_CATEGORIES = (
    ("A", "Category A", 10),
    ("B", "Category B", 20),
    ("C", "Category C", 30),
    ("D", "Category D", 40),
)


def upgrade():
    bind = op.get_bind()
    now = datetime.utcnow()
    for code, label, sort_order in DEFAULT_CATEGORIES:
        bind.execute(
            sa.text(
                """
                INSERT INTO commissioning_punch_category
                    (company_name, project_id, code, label, description, sort_order,
                     is_active, created_by_id, created_at, updated_at)
                SELECT p.company_name, p.id, :code, :label, NULL, :sort_order,
                       :is_active, p.created_by_id, :now, :now
                FROM commissioning_project p
                WHERE NOT EXISTS (
                    SELECT 1 FROM commissioning_punch_category x
                    WHERE x.project_id = p.id AND x.code = :code
                )
                """
            ),
            {"code": code, "label": label, "sort_order": sort_order,
             "is_active": True, "now": now},
        )
    bind.execute(
        sa.text(
            """
            UPDATE commissioning_punch_item
            SET category_code = CAST(category AS VARCHAR(8))
            WHERE category_code IS NULL
            """
        )
    )


def downgrade():
    op.execute(sa.text("UPDATE commissioning_punch_item SET category_code = NULL"))
