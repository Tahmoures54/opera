"""Tenant-scoped OPERA document numbering using MaterialHub counters."""
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import DocumentSequence
from models_commissioning import CheckSheetType, PunchCategory

CHECKSHEET_KEYS = {
    CheckSheetType.PRE_COMM_A: "CS-PREA",
    CheckSheetType.PRE_COMM_B: "CS-PREB",
    CheckSheetType.COMM_C: "CS-COMC",
    CheckSheetType.FUNCTIONAL_TEST: "CS-FUNC",
    CheckSheetType.HYDROTEST: "CS-HYDR",
    CheckSheetType.LEAK_TEST: "CS-LEAK",
    CheckSheetType.FLUSH_BLOW: "CS-FLSH",
    CheckSheetType.MEGGER: "CS-MEGG",
    CheckSheetType.CALIBRATION: "CS-CALB",
}
PUNCH_KEYS = {category: f"PUNCH-{category.value}" for category in PunchCategory}


def _next_value(company_name, key):
    """Initialize a tenant counter safely, then atomically claim its next value."""
    if not company_name:
        raise ValueError("company_name is required for OPERA numbering")
    sequence = db.session.get(DocumentSequence, (key, company_name))
    if sequence is None:
        try:
            with db.session.begin_nested():
                db.session.add(DocumentSequence(key=key, company_name=company_name, last_value=0))
                db.session.flush()
        except IntegrityError:
            # Another transaction initialized the same tenant/key pair.
            pass
    sequence = db.session.get(DocumentSequence, (key, company_name))
    if sequence is None:
        raise RuntimeError(f"Unable to initialize OPERA sequence {key}")
    return sequence.next_value()


def next_checksheet_number(company_name, project_code, sheet_type):
    """Return PROJECT-TYPE-00001 with a tenant/type-specific atomic counter."""
    sheet_type = sheet_type if isinstance(sheet_type, CheckSheetType) else CheckSheetType(sheet_type)
    return f"{project_code}-{sheet_type.value}-{_next_value(company_name, CHECKSHEET_KEYS[sheet_type]):05d}"


def next_punch_number(company_name, project_code, category):
    """Return PROJECT-PUNCH-CATEGORY-00001 with a tenant/category counter."""
    category = category if isinstance(category, PunchCategory) else PunchCategory(category)
    return f"{project_code}-PUNCH-{category.value}-{_next_value(company_name, PUNCH_KEYS[category]):05d}"
