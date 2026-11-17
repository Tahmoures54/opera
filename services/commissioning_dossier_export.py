"""Evidence-based subsystem dossier PDF and ZIP exports.

Exports are point-in-time working packages, not issued or approved contractual dossiers.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

from flask import abort, current_app
from sqlalchemy import and_, or_
from werkzeug.exceptions import HTTPException

from models_commissioning import (
    CheckSheet, CheckSheetStatus, CommissioningAttachment, CommissioningCertificate,
    CommissioningDocument, CommissioningDossierRequirement, CommissioningEquipment,
    CommissioningPreservationInspection, CommissioningPreservationPlan,
    CommissioningProject, CommissioningSubsystem, CommissioningSystem,
    CommissioningTask, DocumentStatus, HandoverPackage, PunchItem, PunchStatus,
    WitnessPoint, WitnessStatus, WitnessType,
)
from services.commissioning_readiness_policy import normalize_readiness_policy
from services.commissioning_storage import read_commissioning_upload


def _iso(value):
    return value.isoformat() if value is not None else None


def _safe_filename(value: str) -> str:
    name = PurePosixPath(str(value).replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return (name or "evidence")[:180]


def build_subsystem_dossier_snapshot(company_name: str, project_id: int, subsystem_id: int) -> tuple[dict, list]:
    """Collect current subsystem records, project policy gates and evidence metadata."""
    project = CommissioningProject.query.filter_by(
        id=project_id, company_name=company_name,
    ).first_or_404()
    subsystem = CommissioningSubsystem.query.join(
        CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id,
    ).filter(
        CommissioningSubsystem.id == subsystem_id,
        CommissioningSubsystem.company_name == company_name,
        CommissioningSystem.project_id == project.id,
    ).first_or_404()
    system = CommissioningSystem.query.filter_by(
        id=subsystem.system_id, company_name=company_name, project_id=project.id,
    ).first_or_404()

    all_documents = CommissioningDocument.query.filter_by(
        company_name=company_name, project_id=project.id, subsystem_id=subsystem.id,
    ).order_by(
        CommissioningDocument.document_number,
        CommissioningDocument.revision_sequence.desc(),
    ).all()
    latest_documents = {}
    for document in all_documents:
        latest_documents.setdefault(document.document_number, document)
    documents = list(latest_documents.values())

    all_sheets = CheckSheet.query.filter_by(
        company_name=company_name, project_id=project.id, subsystem_id=subsystem.id,
    ).order_by(CheckSheet.sheet_number, CheckSheet.revision.desc()).all()
    superseded_sheet_ids = {
        sheet.supersedes_id for sheet in all_sheets if sheet.supersedes_id is not None
    }
    sheets = [sheet for sheet in all_sheets if sheet.id not in superseded_sheet_ids]

    punches = PunchItem.query.filter_by(
        company_name=company_name, project_id=project.id, subsystem_id=subsystem.id,
    ).order_by(PunchItem.punch_number).all()
    tasks = CommissioningTask.query.filter_by(
        company_name=company_name, project_id=project.id, subsystem_id=subsystem.id,
    ).order_by(CommissioningTask.task_number).all()
    equipment = CommissioningEquipment.query.filter_by(
        company_name=company_name, project_id=project.id, subsystem_id=subsystem.id,
    ).order_by(CommissioningEquipment.tag_number).all()
    witnesses = WitnessPoint.query.join(
        CheckSheet, CheckSheet.id == WitnessPoint.check_sheet_id,
    ).filter(
        WitnessPoint.company_name == company_name,
        WitnessPoint.project_id == project.id,
        CheckSheet.subsystem_id == subsystem.id,
    ).order_by(WitnessPoint.scheduled_at).all()
    packages = HandoverPackage.query.filter_by(
        company_name=company_name, project_id=project.id, subsystem_id=subsystem.id,
    ).order_by(HandoverPackage.package_number).all()
    certificates = CommissioningCertificate.query.filter_by(
        company_name=company_name, project_id=project.id, subsystem_id=subsystem.id,
    ).order_by(CommissioningCertificate.certificate_date, CommissioningCertificate.id).all()

    equipment_ids = [item.id for item in equipment]
    preservation_plans = CommissioningPreservationPlan.query.filter(
        CommissioningPreservationPlan.company_name == company_name,
        CommissioningPreservationPlan.project_id == project.id,
        CommissioningPreservationPlan.equipment_id.in_(equipment_ids or [-1]),
    ).order_by(CommissioningPreservationPlan.plan_number).all()
    plan_ids = [item.id for item in preservation_plans]
    preservation_inspections = CommissioningPreservationInspection.query.filter(
        CommissioningPreservationInspection.company_name == company_name,
        CommissioningPreservationInspection.project_id == project.id,
        CommissioningPreservationInspection.plan_id.in_(plan_ids or [-1]),
    ).order_by(
        CommissioningPreservationInspection.performed_at,
        CommissioningPreservationInspection.id,
    ).all()

    entity_ids = {
        "CommissioningDocument": [item.id for item in documents],
        "CheckSheet": [item.id for item in sheets],
        "PunchItem": [item.id for item in punches],
        "HandoverPackage": [item.id for item in packages],
        "CommissioningPreservationInspection": [item.id for item in preservation_inspections],
    }
    attachment_clauses = [
        and_(
            CommissioningAttachment.entity_type == entity_type,
            CommissioningAttachment.entity_id.in_(ids),
        )
        for entity_type, ids in entity_ids.items() if ids
    ]
    attachments = CommissioningAttachment.query.filter(
        CommissioningAttachment.company_name == company_name,
        or_(*attachment_clauses) if attachment_clauses else False,
    ).order_by(
        CommissioningAttachment.entity_type,
        CommissioningAttachment.entity_id,
        CommissioningAttachment.uploaded_at,
        CommissioningAttachment.id,
    ).all()

    evidence_by_document = {}
    for attachment in attachments:
        if attachment.entity_type == "CommissioningDocument":
            evidence_by_document.setdefault(attachment.entity_id, []).append(attachment)

    requirements = CommissioningDossierRequirement.query.filter_by(
        company_name=company_name, project_id=project.id, is_active=True,
    ).order_by(
        CommissioningDossierRequirement.document_type,
        CommissioningDossierRequirement.discipline,
    ).all()
    document_rules = []
    if requirements:
        for rule in requirements:
            matching = [
                item for item in documents
                if item.document_type.strip().casefold() == rule.document_type.strip().casefold()
                and (
                    rule.discipline == "ANY"
                    or item.discipline.strip().casefold() == rule.discipline.strip().casefold()
                )
            ]
            qualifying = [
                item for item in matching
                if (not rule.require_approved or item.status == DocumentStatus.APPROVED)
                and (not rule.require_evidence or bool(evidence_by_document.get(item.id)))
            ]
            document_rules.append({
                "document_type": rule.document_type,
                "discipline": rule.discipline,
                "minimum_count": rule.minimum_count,
                "qualifying_count": len(qualifying),
                "require_approved": rule.require_approved,
                "require_evidence": rule.require_evidence,
                "passed": len(qualifying) >= rule.minimum_count,
            })
        document_gate_passed = all(rule["passed"] for rule in document_rules)
    else:
        document_gate_passed = bool(documents) and all(
            item.status == DocumentStatus.APPROVED for item in documents
        )
        document_rules = [{
            "document_type": "Current engineering documents",
            "discipline": "ANY",
            "minimum_count": 1,
            "qualifying_count": sum(1 for item in documents if item.status == DocumentStatus.APPROVED),
            "require_approved": True,
            "require_evidence": False,
            "passed": document_gate_passed,
        }]

    policy, policy_errors = normalize_readiness_policy(project.readiness_policy_json)
    blocking_categories = set(policy["punch_blocking_categories"]["MC"])
    open_blocking_punches = [
        item for item in punches
        if item.category.value in blocking_categories
        and item.status in (PunchStatus.OPEN, PunchStatus.IN_PROGRESS)
    ]
    pending_holds = [
        item for item in witnesses
        if "MC" in policy["hold_point_blocking_gates"]
        and item.type == WitnessType.HOLD
        and item.status not in (WitnessStatus.RELEASED, WitnessStatus.CANCELLED)
    ]
    unsigned_sheets = [item for item in sheets if item.status != CheckSheetStatus.SIGNED_OFF]
    gates = [
        {"name": "Current Check Sheets", "passed": bool(sheets) and not unsigned_sheets,
         "detail": f"{len(sheets) - len(unsigned_sheets)} of {len(sheets)} current revisions signed off"},
        {"name": "Configured document index", "passed": document_gate_passed,
         "detail": f"{sum(1 for item in document_rules if item['passed'])} of {len(document_rules)} rules passed"},
        {"name": "MC Punch blockers", "passed": not open_blocking_punches,
         "detail": f"{len(open_blocking_punches)} open blocking Punch items"},
        {"name": "MC Hold points", "passed": not pending_holds,
         "detail": f"{len(pending_holds)} unreleased blocking Hold points"},
        {"name": "Readiness policy", "passed": not policy_errors,
         "detail": "; ".join(policy_errors) if policy_errors else "Valid project policy"},
    ]

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "export_classification": "UNCONTROLLED_WORKING_EXPORT",
        "notice": "Point-in-time OPERA export. Not an issued or approved contractual dossier.",
        "project": {"id": project.id, "code": project.project_code, "name": project.name,
                    "client": project.client, "contractor": project.contractor},
        "system": {"id": system.id, "code": system.system_code, "name": system.name},
        "subsystem": {"id": subsystem.id, "code": subsystem.subsystem_code, "name": subsystem.name},
        "readiness": {
            "gates": gates,
            "document_rules": document_rules,
            "mc_dossier_checks_passed": all(gate["passed"] for gate in gates),
            "policy_errors": policy_errors,
        },
        "counts": {
            "equipment": len(equipment), "documents": len(documents),
            "check_sheets": len(sheets), "punch_items": len(punches),
            "tasks": len(tasks), "witness_points": len(witnesses),
            "preservation_plans": len(preservation_plans),
            "preservation_inspections": len(preservation_inspections),
            "handover_packages": len(packages), "certificates": len(certificates),
            "evidence_files": len(attachments),
        },
        "equipment": [{"tag_number": item.tag_number, "type": item.equipment_type,
                       "description": item.description} for item in equipment],
        "documents": [{"number": item.document_number, "revision": item.revision,
                       "title": item.title, "type": item.document_type,
                       "discipline": item.discipline, "status": item.status.value,
                       "evidence_count": len(evidence_by_document.get(item.id, []))}
                      for item in documents],
        "check_sheets": [{"number": item.sheet_number, "revision": item.revision,
                          "title": item.title, "type": item.sheet_type.value,
                          "status": item.status.value} for item in sheets],
        "punch_items": [{"number": item.punch_number, "category": item.category.value,
                         "severity": item.severity.value, "description": item.description,
                         "status": item.status.value,
                         "corrective_action": item.corrective_action} for item in punches],
        "tasks": [{"number": item.task_number, "activity": item.activity_type.value,
                   "title": item.title, "discipline": item.discipline,
                   "status": item.status.value} for item in tasks],
        "witness_points": [{"type": item.type.value, "status": item.status.value,
                            "scheduled_at": _iso(item.scheduled_at),
                            "result": item.result, "remarks": item.remarks} for item in witnesses],
        "preservation_plans": [{"plan_number": item.plan_number, "activity": item.activity,
                                "procedure_reference": item.procedure_reference,
                                "procedure_revision": item.procedure_revision,
                                "interval_days": item.interval_days,
                                "next_due_date": _iso(item.next_due_date),
                                "status": item.status} for item in preservation_plans],
        "preservation_inspections": [{"performed_at": _iso(item.performed_at),
                                      "result": item.result, "findings": item.findings,
                                      "corrective_action": item.corrective_action,
                                      "procedure_reference": item.procedure_reference_snapshot,
                                      "procedure_revision": item.procedure_revision_snapshot}
                                     for item in preservation_inspections],
        "handover_packages": [{"package_number": item.package_number, "status": item.status.value,
                               "accepted_by_operations": item.accepted_by_operations}
                              for item in packages],
        "certificates": [{"type": item.certificate_type, "number": item.certificate_number,
                          "date": _iso(item.certificate_date), "issued_at": _iso(item.issued_at),
                          "snapshot": item.snapshot_json} for item in certificates],
        "evidence": [{
            "id": item.id, "entity_type": item.entity_type, "entity_id": item.entity_id,
            "filename": item.filename, "mime_type": item.mime_type,
            "file_size": item.file_size, "sha256": item.checksum,
            "uploaded_at": _iso(item.uploaded_at),
        } for item in attachments],
    }
    return snapshot, attachments


def _pdf_text(value) -> str:
    """Escape untrusted record text for ReportLab Paragraph markup."""
    text = str(value if value is not None else "—").replace("\n", " ")
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace(chr(34), "&quot;").replace(chr(39), "&#x27;"))


def render_subsystem_dossier_pdf(snapshot: dict) -> bytes:
    """Render a printable working dossier summary with an explicit status notice."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Dossier PDF export requires reportlab.") from exc

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), rightMargin=14 * mm, leftMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title="OPERA Subsystem Completion Dossier", author="OPERA",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="DossierTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=17))
    styles.add(ParagraphStyle(name="DossierNotice", parent=styles["BodyText"], textColor=colors.darkred, fontSize=8))
    cell_style = ParagraphStyle(name="DossierCell", parent=styles["BodyText"], fontSize=7, leading=9)
    story = [
        Paragraph("OPERA — Subsystem Completion Dossier", styles["DossierTitle"]),
        Spacer(1, 5 * mm),
        Paragraph(snapshot["notice"], styles["DossierNotice"]),
        Spacer(1, 3 * mm),
        Paragraph(
            f"<b>Project:</b> {_pdf_text(snapshot['project']['code'])} — {_pdf_text(snapshot['project']['name'])}"
            f" &nbsp;&nbsp; <b>System:</b> {_pdf_text(snapshot['system']['code'])}"
            f" &nbsp;&nbsp; <b>Subsystem:</b> {_pdf_text(snapshot['subsystem']['code'])} — {_pdf_text(snapshot['subsystem']['name'])}",
            styles["BodyText"],
        ),
        Paragraph(f"<b>Generated:</b> {_pdf_text(snapshot['generated_at'])}", styles["BodyText"]),
        Spacer(1, 4 * mm),
    ]

    def add_table(title, headers, rows):
        story.append(Paragraph(title, styles["Heading2"]))
        if not rows:
            story.append(Paragraph("No records registered.", styles["BodyText"]))
            story.append(Spacer(1, 2 * mm))
            return
        data = [[Paragraph(_pdf_text(str(value)), cell_style) for value in headers]]
        data.extend([
            [Paragraph(_pdf_text(str(value if value is not None else "—")), cell_style) for value in row]
            for row in rows
        ])
        table = Table(data, colWidths=[document.width / len(headers)] * len(headers), repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#24364b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fa")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        story.append(Spacer(1, 3 * mm))

    add_table("Readiness and dossier checks", ["Check", "Result", "Details"], [
        (gate["name"], "PASS" if gate["passed"] else "OPEN", gate["detail"])
        for gate in snapshot["readiness"]["gates"]
    ])
    add_table("Equipment / Tag Register", ["Tag", "Type", "Description"], [
        (item["tag_number"], item["type"], item["description"]) for item in snapshot["equipment"]
    ])
    add_table("Current Engineering Documents", ["Number", "Rev", "Title", "Type", "Discipline", "Status", "Evidence"], [
        (item["number"], item["revision"], item["title"], item["type"],
         item["discipline"], item["status"], item["evidence_count"]) for item in snapshot["documents"]
    ])
    add_table("Check Sheets", ["Number", "Rev", "Title", "Type", "Status"], [
        (item["number"], item["revision"], item["title"], item["type"], item["status"])
        for item in snapshot["check_sheets"]
    ])
    add_table("Punch List", ["Number", "Cat.", "Severity", "Description", "Status", "Corrective action"], [
        (item["number"], item["category"], item["severity"], item["description"],
         item["status"], item["corrective_action"]) for item in snapshot["punch_items"]
    ])
    add_table("Commissioning Tasks", ["Number", "Activity", "Title", "Discipline", "Status"], [
        (item["number"], item["activity"], item["title"], item["discipline"], item["status"])
        for item in snapshot["tasks"]
    ])
    add_table("Preservation Plans", ["Plan", "Activity", "Procedure", "Rev.", "Interval days", "Next due", "Status"], [
        (item["plan_number"], item["activity"], item["procedure_reference"],
         item["procedure_revision"], item["interval_days"], item["next_due_date"], item["status"])
        for item in snapshot["preservation_plans"]
    ])
    add_table("Handover Certificates", ["Type", "Number", "Date", "Issued at"], [
        (item["type"], item["number"], item["date"], item["issued_at"])
        for item in snapshot["certificates"]
    ])
    add_table("Evidence Index", ["ID", "Entity", "File", "Size", "SHA-256"], [
        (item["id"], f"{item['entity_type']} #{item['entity_id']}",
         item["filename"], item["file_size"], item["sha256"]) for item in snapshot["evidence"]
    ])
    document.build(story)
    return buffer.getvalue()


def render_subsystem_dossier_zip(snapshot: dict, attachments: list) -> bytes:
    """Build a ZIP containing the PDF, JSON manifest and checksum-verified evidence."""
    pdf_bytes = render_subsystem_dossier_pdf(snapshot)
    max_total = int(current_app.config.get("OPERA_DOSSIER_EXPORT_MAX_BYTES") or 100 * 1024 * 1024)
    declared_total = sum(int(item.file_size or 0) for item in attachments)
    if declared_total > max_total:
        abort(413, description="Dossier evidence exceeds the configured export size limit.")

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("dossier.pdf", pdf_bytes)
        archive.writestr("manifest.json", json.dumps(snapshot, ensure_ascii=False, indent=2, default=str))
        for item in attachments:
            try:
                content = read_commissioning_upload(item.storage_key)
            except HTTPException:
                abort(409, description=f"Evidence file {item.filename} is missing from storage; the dossier package was not generated.")
            if hashlib.sha256(content).hexdigest() != item.checksum:
                abort(409, description=f"Evidence checksum mismatch for {item.filename}; the dossier package was not generated.")
            archive_name = PurePosixPath(
                "evidence", item.entity_type, str(item.entity_id),
                f"{item.id}-{_safe_filename(item.filename)}",
            ).as_posix()
            archive.writestr(archive_name, content)
    if buffer.tell() > max_total + 10 * 1024 * 1024:
        abort(413, description="Generated dossier package exceeds the configured export size limit.")
    return buffer.getvalue()
