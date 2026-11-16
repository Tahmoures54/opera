"""Tenant-scoped OPERA document number allocation tests."""
import pytest
from services.commissioning_number_service import next_checksheet_number, next_punch_number
from models_commissioning import CheckSheetType, PunchCategory


@pytest.fixture(autouse=True)
def _application_context(app):
    with app.app_context():
        yield


def test_checksheet_numbers_increment_per_tenant_and_type(app):
    assert next_checksheet_number("Contractor A", "RFY-12", CheckSheetType.PRE_COMM_A) == "RFY-12-PRE_COMM_A-00001"
    assert next_checksheet_number("Contractor A", "RFY-12", CheckSheetType.PRE_COMM_A) == "RFY-12-PRE_COMM_A-00002"
    assert next_checksheet_number("Contractor A", "RFY-12", CheckSheetType.COMM_C) == "RFY-12-COMM_C-00001"
    assert next_checksheet_number("Contractor B", "RFY-12", CheckSheetType.PRE_COMM_A) == "RFY-12-PRE_COMM_A-00001"


def test_punch_numbers_increment_per_tenant_and_category(app):
    assert next_punch_number("Contractor A", "RFY-12", PunchCategory.A) == "RFY-12-PUNCH-A-00001"
    assert next_punch_number("Contractor A", "RFY-12", PunchCategory.A) == "RFY-12-PUNCH-A-00002"
    assert next_punch_number("Contractor A", "RFY-12", PunchCategory.B) == "RFY-12-PUNCH-B-00001"
