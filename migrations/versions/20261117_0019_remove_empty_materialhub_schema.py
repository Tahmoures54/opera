"""Drop the unused MaterialHub schema after an empty-data safety check.

Revision ID: 20261117_0019
Revises: 20261116_0019
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0019"
down_revision = "20261116_0019"
branch_labels = None
depends_on = None

# Child tables precede their parents so this also works with FK enforcement.
LEGACY_TABLES = (
    # Deep dependants first (including tables that no longer have ORM mappings).
    "three_way_match",
    "bid",
    "rfq_supplier",
    "material_document",
    "osd_report_line",
    "osd_report",
    "quality_control",
    "warehouse_transaction",
    "warehouse_inventory",
    "goods_receipt_line",
    "goods_receipt",
    "packing_list_line",
    "packing_list",
    "supplier_invoice",
    "material_receipt",
    "purchase_order_item",
    "delivery",
    "rfq",
    "tender",
    "approval",
    "material_requisition",
    "supplier_material",
    "supplier_score",
    "material_price_history",
    "material_trace",
    "schedule_risk",
    "report_share",
    "material_request",
    "purchase_order",
    "material_master",
    "project",
)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    present = [name for name in LEGACY_TABLES if name in existing]

    # Never discard unexpected records. The user table itself is preserved.
    populated = []
    for name in present:
        table = sa.Table(name, sa.MetaData(), autoload_with=bind)
        count = bind.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()
        if count:
            populated.append(f"{name}={count}")
    if populated:
        raise RuntimeError(
            "MaterialHub schema cleanup stopped: legacy tables contain records "
            "and require an explicit export/retention decision: " + ", ".join(populated)
        )

    user_columns = {column["name"] for column in inspector.get_columns("user")} if "user" in existing else set()
    if "user" in existing:
        legacy_user_columns = [name for name in ("project_id", "store_name") if name in user_columns]
        if legacy_user_columns:
            predicates = " OR ".join(f'"{name}" IS NOT NULL' for name in legacy_user_columns)
            remaining = bind.exec_driver_sql(
                f'SELECT COUNT(*) FROM "user" WHERE {predicates}'
            ).scalar_one()
            if remaining:
                raise RuntimeError(
                    "MaterialHub schema cleanup stopped: user.project_id/store_name "
                    "still contain values; export or review them before removal."
                )
            with op.batch_alter_table("user") as batch:
                for name in legacy_user_columns:
                    batch.drop_column(name)

    for name in present:
        op.drop_table(name)


def downgrade():
    raise RuntimeError(
        "This migration intentionally removes obsolete MaterialHub tables. "
        "Restore from a verified backup rather than recreating empty legacy tables."
    )
