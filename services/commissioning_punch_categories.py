"""Project-defined Punch category helpers (P2: defaults and dual write).

Historical A-D categories are created as neutral labels. Their meaning is
not implied: projects define what each code means in their own procedures.
"""
from datetime import datetime

from extensions import db
from models_commissioning import CommissioningPunchCategory

DEFAULT_PUNCH_CATEGORIES = (
    ("A", "Category A", 10),
    ("B", "Category B", 20),
    ("C", "Category C", 30),
    ("D", "Category D", 40),
)


def ensure_default_punch_categories(company_name, project_id, created_by_id=None):
    """Create missing default categories for a project. Idempotent.

    Existing definitions are never modified, so renamed or deactivated
    categories set by the project are preserved.
    """
    existing = {
        row.code for row in CommissioningPunchCategory.query.filter_by(
            company_name=company_name, project_id=project_id,
        ).all()
    }
    now = datetime.utcnow()
    created = []
    for code, label, sort_order in DEFAULT_PUNCH_CATEGORIES:
        if code in existing:
            continue
        category = CommissioningPunchCategory(
            company_name=company_name, project_id=project_id, code=code, label=label,
            sort_order=sort_order, is_active=True, created_by_id=created_by_id,
            created_at=now, updated_at=now,
        )
        db.session.add(category)
        created.append(code)
    return created
