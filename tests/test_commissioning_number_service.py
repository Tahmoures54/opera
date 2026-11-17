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


    
def test_checksheet_number_allocation_is_concurrency_safe_on_postgresql():
    """Concurrent first-use allocations produce unique, gap-free tenant numbers."""
    import os
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import uuid4

    from app import create_app
    from extensions import db
    from models import DocumentSequence

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("Requires the PostgreSQL integration database")

    production_app = create_app("production")
    company_name = f"OPERA-SEQ-RACE-{uuid4().hex}"
    project_code = "RACE"
    worker_count = 8
    start = Barrier(worker_count)

    def allocate_number(_):
        with production_app.app_context():
            try:
                start.wait(timeout=20)
                number = next_checksheet_number(
                    company_name, project_code, CheckSheetType.COMM_C
                )
                db.session.commit()
                return number
            except Exception:
                db.session.rollback()
                raise
            finally:
                db.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            numbers = list(pool.map(allocate_number, range(worker_count)))

        expected = [
            f"{project_code}-COMM_C-{sequence:05d}"
            for sequence in range(1, worker_count + 1)
        ]
        assert sorted(numbers) == expected

        with production_app.app_context():
            counter = db.session.get(DocumentSequence, ("CS-COMC", company_name))
            assert counter is not None
            assert counter.last_value == worker_count
    finally:
        with production_app.app_context():
            counter = db.session.get(DocumentSequence, ("CS-COMC", company_name))
            if counter is not None:
                db.session.delete(counter)
                db.session.commit()
            db.session.remove()
            db.engine.dispose()
