"""Create a bounded OPERA demo dataset.

Usage:
  SEED_COMMISSIONING_DEMO=1 python scripts/seed_commissioning_demo.py \
      --company "Demo Contractor" --user-id 123

The script never creates users and refuses to run unless explicitly enabled.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from extensions import db
from models import User
from services.commissioning_number_service import next_checksheet_number, next_punch_number
from models_commissioning import (
    CheckSheet, CheckSheetItem, CheckSheetType, CheckSheetStatus,
    CommissioningEquipment, CommissioningMembership, CommissioningProject,
    CommissioningSubsystem, CommissioningSystem, ItemResultStatus,
    MembershipRole, PunchCategory, PunchItem, PunchSeverity, PunchStatus,
)


def main():
    parser = argparse.ArgumentParser(description="Seed an OPERA commissioning demo project")
    parser.add_argument("--company", required=True, help="Existing organization company_name")
    parser.add_argument("--user-id", required=True, type=int, help="Existing user ID in that company")
    parser.add_argument("--project-code", default="OPERA-DEMO")
    args = parser.parse_args()

    if os.getenv("SEED_COMMISSIONING_DEMO") != "1":
        raise SystemExit("Refusing to seed: set SEED_COMMISSIONING_DEMO=1 explicitly.")

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(id=args.user_id, company_name=args.company).first()
        if user is None:
            raise SystemExit("The selected user does not exist in the requested company.")
        if CommissioningProject.query.filter_by(company_name=args.company, project_code=args.project_code).first():
            raise SystemExit("A project with this company and project code already exists; no changes made.")

        project = CommissioningProject(
            company_name=args.company,
            project_code=args.project_code,
            name="OPERA Demonstration Project",
            client="Demo Client",
            contractor=args.company,
            created_by_id=user.id,
        )
        db.session.add(project)
        db.session.flush()
        system = CommissioningSystem(company_name=args.company, project_id=project.id, system_code="SYS-UTIL", name="Utilities", weight_percent=100)
        db.session.add(system)
        db.session.flush()
        subsystems = []
        for code, name, weight in (("SS-AIR", "Instrument Air", 60), ("SS-WTR", "Service Water", 40)):
            subsystem = CommissioningSubsystem(company_name=args.company, system_id=system.id, subsystem_code=code, name=name, weight_percent=weight)
            db.session.add(subsystem)
            subsystems.append(subsystem)
        db.session.flush()

        equipment_specs = [
            (subsystems[0], "K-1001", "Air Compressor"),
            (subsystems[0], "V-1002", "Air Receiver"),
            (subsystems[1], "P-2001", "Service Water Pump"),
        ]
        equipment = []
        for subsystem, tag, kind in equipment_specs:
            row = CommissioningEquipment(company_name=args.company, project_id=project.id, subsystem_id=subsystem.id, tag_number=tag, equipment_type=kind)
            db.session.add(row)
            equipment.append(row)
        db.session.flush()

        sheet_types = [CheckSheetType.PRE_COMM_A, CheckSheetType.PRE_COMM_B, CheckSheetType.COMM_C, CheckSheetType.FUNCTIONAL_TEST, CheckSheetType.COMM_C]
        for index, sheet_type in enumerate(sheet_types, start=1):
            subsystem = subsystems[(index - 1) % len(subsystems)]
            tag = equipment[(index - 1) % len(equipment)]
            sheet = CheckSheet(
                company_name=args.company, project_id=project.id, system_id=system.id,
                subsystem_id=subsystem.id, equipment_id=tag.id,
                sheet_number=next_checksheet_number(args.company, args.project_code, sheet_type),
                sheet_type=sheet_type, revision=0, title=f"{tag.tag_number} - {sheet_type.value}",
                status=CheckSheetStatus.DRAFT, created_by_id=user.id,
            )
            db.session.add(sheet)
            db.session.flush()
            for sequence, description in enumerate(("Visual inspection", "Verify installation", "Record test result"), start=1):
                db.session.add(CheckSheetItem(company_name=args.company, check_sheet_id=sheet.id, sequence=sequence, description=description, result_status=ItemResultStatus.PENDING))

        for index in range(1, 9):
            subsystem = subsystems[(index - 1) % len(subsystems)]
            tag = equipment[(index - 1) % len(equipment)]
            category = list(PunchCategory)[(index - 1) % len(PunchCategory)]
            db.session.add(PunchItem(
                company_name=args.company, project_id=project.id, subsystem_id=subsystem.id,
                equipment_id=tag.id, punch_number=next_punch_number(args.company, args.project_code, category),
                category=category, severity=PunchSeverity.MEDIUM,
                description=f"Demonstration deficiency {index}", raised_by_id=user.id,
                status=PunchStatus.OPEN,
            ))

        db.session.add(CommissioningMembership(
            company_name=args.company, project_id=project.id, user_id=user.id,
            role=MembershipRole.COMMISSIONING_MANAGER, is_active=True, created_by_id=user.id,
        ))
        db.session.commit()
        print(f"Created OPERA demo project {project.project_code} (id={project.id}) for {args.company}.")


if __name__ == "__main__":
    main()
