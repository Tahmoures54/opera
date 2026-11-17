from extensions import db
import models  # noqa: F401
import models_commissioning  # noqa: F401


def test_only_opera_and_shared_identity_models_are_registered():
    retired_tables = {
        "material_document",
        "material_price_history",
        "material_trace",
        "schedule_risk",
        "supplier_score",
        "supplier_invoice",
        "material_receipt",
        "rfq",
        "rfq_supplier",
        "three_way_match",
        "project",
        "material_requisition",
        "material_master",
        "supplier_material",
        "purchase_order",
        "purchase_order_item",
        "quality_control",
        "delivery",
        "packing_list",
        "packing_list_line",
        "goods_receipt",
        "goods_receipt_line",
        "osd_report",
        "osd_report_line",
        "warehouse_inventory",
        "warehouse_transaction",
        "approval",
        "tender",
        "bid",
        "report_share",
        "material_request",
    }
    assert retired_tables.isdisjoint(db.metadata.tables)
    assert {"user", "account_recovery_token", "contact_inquiry", "document_sequence"}.issubset(db.metadata.tables)


def test_user_model_no_longer_exposes_materialhub_workspace_columns():
    from models import User

    assert "project_id" not in User.__table__.columns
    assert "store_name" not in User.__table__.columns
