"""Validated Excel exchange for OPERA commissioning engineering registers.

The workbook format is OPERA-owned and versioned; it is not represented as an
official ICAPS template. Imports are create-only and dry-run validated first.
"""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy.exc import IntegrityError

from extensions import db
from models_commissioning import (
    CommissioningEquipment, CommissioningProject, CommissioningSubsystem,
    CommissioningSystem, CommissioningTask, CommissioningTaskStatus,
    CommissioningTaskType,
)
from services.commissioning_access import add_audit_event, get_project, has_permission
from blueprints.commissioning import commissioning_bp

MAX_WORKBOOK_BYTES = 5 * 1024 * 1024
MAX_ROWS_PER_SHEET = 5000
SHEETS = {
    "Systems": ["system_code", "name", "description", "p_and_id_ref", "weight_percent"],
    "Subsystems": [
        "system_code", "subsystem_code", "name", "description", "weight_percent",
        "mc_target_date", "rf_target_date",
    ],
    "Equipment": [
        "tag_number", "system_code", "subsystem_code", "equipment_type",
        "description", "manufacturer", "model_number", "serial_no", "status",
    ],
    "Tasks": [
        "task_number", "system_code", "subsystem_code", "equipment_tag",
        "activity_type", "title", "description", "discipline", "progress_stage",
        "progress_substage", "assigned_group", "estimated_man_hours",
        "planned_start_date", "planned_finish_date",
    ],
}


def _text(value, limit=500):
    if value is None:
        return ""
    result = str(value).strip()
    return result[:limit]


def _date_value(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def _number(value, field, default=0.0, maximum=None):
    if value in (None, ""):
        return default
    number = float(value)
    if number < 0 or (maximum is not None and number > maximum):
        raise ValueError(f"{field} must be between 0 and {maximum}" if maximum is not None
                         else f"{field} cannot be negative")
    return number


def _workbook_bytes(workbook):
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _style_workbook(workbook):
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="24445D")
        for column in sheet.columns:
            letter = column[0].column_letter
            width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 14), 42)
            sheet.column_dimensions[letter].width = width


def _set_safe(cell, value):
    cell.value = value
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        cell.data_type = "s"


def _new_workbook():
    workbook = Workbook()
    first = workbook.active
    first.title = "Systems"
    for name, headers in SHEETS.items():
        sheet = first if name == "Systems" else workbook.create_sheet(name)
        sheet.append(headers)
    return workbook


def _project_records(project):
    systems = CommissioningSystem.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).order_by(CommissioningSystem.system_code).all()
    subsystems = CommissioningSubsystem.query.join(
        CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id,
    ).filter(
        CommissioningSubsystem.company_name == project.company_name,
        CommissioningSystem.project_id == project.id,
    ).order_by(CommissioningSystem.system_code, CommissioningSubsystem.subsystem_code).all()
    equipment = CommissioningEquipment.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).order_by(CommissioningEquipment.tag_number).all()
    tasks = CommissioningTask.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).order_by(CommissioningTask.task_number).all()
    system_by_id = {item.id: item for item in systems}
    subsystem_by_id = {item.id: item for item in subsystems}
    return systems, subsystems, equipment, tasks, system_by_id, subsystem_by_id


def _export_workbook(project):
    workbook = _new_workbook()
    systems, subsystems, equipment, tasks, system_by_id, subsystem_by_id = _project_records(project)
    for item in systems:
        workbook["Systems"].append([
            item.system_code, item.name, item.description, item.p_and_id_ref, item.weight_percent,
        ])
    for item in subsystems:
        system = system_by_id.get(item.system_id)
        workbook["Subsystems"].append([
            system.system_code if system else "", item.subsystem_code, item.name,
            item.description, item.weight_percent, item.mc_target_date, item.rf_target_date,
        ])
    for item in equipment:
        subsystem = subsystem_by_id.get(item.subsystem_id)
        system = system_by_id.get(subsystem.system_id) if subsystem else None
        workbook["Equipment"].append([
            item.tag_number, system.system_code if system else "",
            subsystem.subsystem_code if subsystem else "", item.equipment_type,
            item.description, item.manufacturer, item.model_number, item.serial_no, item.status,
        ])
    for item in tasks:
        subsystem = subsystem_by_id.get(item.subsystem_id)
        system = system_by_id.get(item.system_id)
        equipment_tag = next((eq.tag_number for eq in equipment if eq.id == item.equipment_id), "")
        workbook["Tasks"].append([
            item.task_number, system.system_code if system else "",
            subsystem.subsystem_code if subsystem else "", equipment_tag,
            item.activity_type.value, item.title, item.description, item.discipline,
            item.progress_stage, item.progress_substage, item.assigned_group,
            item.estimated_man_hours, item.planned_start_date, item.planned_finish_date,
        ])
    _style_workbook(workbook)
    return _workbook_bytes(workbook)


def _read_rows(workbook, errors):
    parsed = {}
    for sheet_name, headers in SHEETS.items():
        if sheet_name not in workbook.sheetnames:
            errors.append({"sheet": sheet_name, "row": 1, "field": "sheet",
                           "message": "Required worksheet is missing."})
            parsed[sheet_name] = []
            continue
        sheet = workbook[sheet_name]
        header_values = [_text(value, 80).lower().replace(" ", "_") for value in next(
            sheet.iter_rows(min_row=1, max_row=1, values_only=True), (),
        )]
        if len(header_values) != len(set(header_values)):
            errors.append({"sheet": sheet_name, "row": 1, "field": "headers",
                           "message": "Duplicate column names are not allowed."})
            parsed[sheet_name] = []
            continue
        missing = [name for name in headers if name not in header_values]
        if missing:
            errors.append({"sheet": sheet_name, "row": 1, "field": "headers",
                           "message": "Missing columns: " + ", ".join(missing)})
            parsed[sheet_name] = []
            continue
        indices = {name: header_values.index(name) for name in headers}
        rows = []
        for row_number, values in enumerate(
            sheet.iter_rows(min_row=2, values_only=True), start=2,
        ):
            if row_number > MAX_ROWS_PER_SHEET + 1:
                errors.append({"sheet": sheet_name, "row": row_number, "field": "row",
                               "message": f"Maximum {MAX_ROWS_PER_SHEET} data rows exceeded."})
                break
            if not any(value not in (None, "") for value in values):
                continue
            rows.append({
                "_row": row_number,
                **{name: values[index] if index < len(values) else None
                   for name, index in indices.items()},
            })
        parsed[sheet_name] = rows
    return parsed


def _validate_import(project, parsed):
    errors = []
    systems, subsystems, equipment, tasks, system_by_id, subsystem_by_id = _project_records(project)
    existing_systems = {item.system_code: item for item in systems}
    existing_subsystems = {
        (system_by_id[item.system_id].system_code, item.subsystem_code): item
        for item in subsystems if item.system_id in system_by_id
    }
    existing_equipment = {item.tag_number for item in equipment}
    existing_tasks = {
        item.task_number for item in CommissioningTask.query.filter_by(
            company_name=project.company_name,
        ).all()
    }

    valid_systems = []
    system_codes = set(existing_systems)
    for row in parsed["Systems"]:
        start = len(errors)
        code, name = _text(row["system_code"], 50), _text(row["name"], 200)
        if not code:
            errors.append({"sheet": "Systems", "row": row["_row"], "field": "system_code", "message": "Required."})
        elif code in system_codes:
            errors.append({"sheet": "Systems", "row": row["_row"], "field": "system_code", "message": "System code already exists; imports are create-only."})
        if not name:
            errors.append({"sheet": "Systems", "row": row["_row"], "field": "name", "message": "Required."})
        try:
            weight = _number(row["weight_percent"], "weight_percent", 0.0, 100.0)
        except (TypeError, ValueError) as exc:
            errors.append({"sheet": "Systems", "row": row["_row"], "field": "weight_percent", "message": str(exc)})
            weight = 0.0
        if len(errors) == start:
            system_codes.add(code)
            valid_systems.append({
                **row, "system_code": code, "name": name, "weight_percent": weight,
                "description": _text(row["description"], 2000),
                "p_and_id_ref": _text(row["p_and_id_ref"], 200),
            })

    valid_subsystems = []
    subsystem_keys = set(existing_subsystems)
    for row in parsed["Subsystems"]:
        start = len(errors)
        system_code = _text(row["system_code"], 50)
        code, name = _text(row["subsystem_code"], 50), _text(row["name"], 200)
        if system_code not in system_codes:
            errors.append({"sheet": "Subsystems", "row": row["_row"], "field": "system_code", "message": "System does not exist in this project or workbook."})
        if not code:
            errors.append({"sheet": "Subsystems", "row": row["_row"], "field": "subsystem_code", "message": "Required."})
        elif (system_code, code) in subsystem_keys:
            errors.append({"sheet": "Subsystems", "row": row["_row"], "field": "subsystem_code", "message": "Subsystem code already exists under this system."})
        if not name:
            errors.append({"sheet": "Subsystems", "row": row["_row"], "field": "name", "message": "Required."})
        try:
            weight = _number(row["weight_percent"], "weight_percent", 0.0, 100.0)
            mc_date, rf_date = _date_value(row["mc_target_date"]), _date_value(row["rf_target_date"])
        except (TypeError, ValueError) as exc:
            errors.append({"sheet": "Subsystems", "row": row["_row"], "field": "dates/weight", "message": str(exc)})
            weight, mc_date, rf_date = 0.0, None, None
        if len(errors) == start:
            subsystem_keys.add((system_code, code))
            valid_subsystems.append({
                **row, "system_code": system_code, "subsystem_code": code, "name": name,
                "weight_percent": weight, "mc_target_date": mc_date, "rf_target_date": rf_date,
                "description": _text(row["description"], 2000),
            })

    valid_equipment = []
    equipment_tags = set(existing_equipment)
    subsystem_keys_all = subsystem_keys
    for row in parsed["Equipment"]:
        start = len(errors)
        tag = _text(row["tag_number"], 100)
        system_code = _text(row["system_code"], 50)
        subsystem_code = _text(row["subsystem_code"], 50)
        equipment_type = _text(row["equipment_type"], 100)
        if not tag:
            errors.append({"sheet": "Equipment", "row": row["_row"], "field": "tag_number", "message": "Required."})
        elif tag in equipment_tags:
            errors.append({"sheet": "Equipment", "row": row["_row"], "field": "tag_number", "message": "Equipment tag already exists in this project."})
        if (system_code, subsystem_code) not in subsystem_keys_all:
            errors.append({"sheet": "Equipment", "row": row["_row"], "field": "subsystem_code", "message": "Subsystem reference does not exist under the selected system."})
        if not equipment_type:
            errors.append({"sheet": "Equipment", "row": row["_row"], "field": "equipment_type", "message": "Required."})
        if len(errors) == start:
            equipment_tags.add(tag)
            valid_equipment.append({
                **row, "tag_number": tag, "system_code": system_code,
                "subsystem_code": subsystem_code, "equipment_type": equipment_type,
                "description": _text(row["description"], 2000),
                "manufacturer": _text(row["manufacturer"], 150),
                "model_number": _text(row["model_number"], 100),
                "serial_no": _text(row["serial_no"], 100),
                "status": _text(row["status"], 30).upper() or "ACTIVE",
            })

    valid_tasks = []
    task_numbers = set(existing_tasks)
    activity_values = {item.value for item in CommissioningTaskType}
    equipment_tag_refs = set(equipment_tags)
    for row in parsed["Tasks"]:
        start = len(errors)
        number = _text(row["task_number"], 100)
        system_code = _text(row["system_code"], 50)
        subsystem_code = _text(row["subsystem_code"], 50)
        equipment_tag = _text(row["equipment_tag"], 100)
        activity = _text(row["activity_type"], 20).upper()
        title, discipline = _text(row["title"], 200), _text(row["discipline"], 80)
        if not number:
            errors.append({"sheet": "Tasks", "row": row["_row"], "field": "task_number", "message": "Required."})
        elif number in task_numbers:
            errors.append({"sheet": "Tasks", "row": row["_row"], "field": "task_number", "message": "Task number already exists in this company."})
        if (system_code, subsystem_code) not in subsystem_keys_all:
            errors.append({"sheet": "Tasks", "row": row["_row"], "field": "subsystem_code", "message": "Subsystem reference does not exist under the selected system."})
        if equipment_tag and equipment_tag not in equipment_tag_refs:
            errors.append({"sheet": "Tasks", "row": row["_row"], "field": "equipment_tag", "message": "Equipment tag does not exist in this project or workbook."})
        if activity not in activity_values:
            errors.append({"sheet": "Tasks", "row": row["_row"], "field": "activity_type", "message": "Use one of: " + ", ".join(sorted(activity_values))})
        if not title:
            errors.append({"sheet": "Tasks", "row": row["_row"], "field": "title", "message": "Required."})
        if not discipline:
            errors.append({"sheet": "Tasks", "row": row["_row"], "field": "discipline", "message": "Required."})
        try:
            hours = _number(row["estimated_man_hours"], "estimated_man_hours", 0.0)
            start_date, finish_date = _date_value(row["planned_start_date"]), _date_value(row["planned_finish_date"])
            if start_date and finish_date and finish_date < start_date:
                raise ValueError("planned_finish_date cannot be before planned_start_date.")
        except (TypeError, ValueError) as exc:
            errors.append({"sheet": "Tasks", "row": row["_row"], "field": "hours/dates", "message": str(exc)})
            hours, start_date, finish_date = 0.0, None, None
        if len(errors) == start:
            task_numbers.add(number)
            valid_tasks.append({
                **row, "task_number": number, "system_code": system_code,
                "subsystem_code": subsystem_code, "equipment_tag": equipment_tag,
                "activity_type": activity, "title": title, "discipline": discipline,
                "estimated_man_hours": hours, "planned_start_date": start_date,
                "planned_finish_date": finish_date, "description": _text(row["description"], 3000),
                "progress_stage": _text(row["progress_stage"], 80),
                "progress_substage": _text(row["progress_substage"], 80),
                "assigned_group": _text(row["assigned_group"], 120),
            })

    return {
        "systems": valid_systems, "subsystems": valid_subsystems,
        "equipment": valid_equipment, "tasks": valid_tasks,
    }, errors


def _import_workbook(project, planned):
    systems = {
        item.system_code: item for item in CommissioningSystem.query.filter_by(
            company_name=project.company_name, project_id=project.id,
        ).all()
    }
    subsystems = {
        (systems_by_id.system_code, item.subsystem_code): item
        for item in CommissioningSubsystem.query.join(
            CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id,
        ).filter(
            CommissioningSubsystem.company_name == project.company_name,
            CommissioningSystem.project_id == project.id,
        ).all()
        for systems_by_id in [systems.get(systems_by_id.system_code) if False else None]
    } if False else {}
    for item in CommissioningSubsystem.query.join(
        CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id,
    ).filter(
        CommissioningSubsystem.company_name == project.company_name,
        CommissioningSystem.project_id == project.id,
    ).all():
        parent = CommissioningSystem.query.filter_by(
            id=item.system_id, company_name=project.company_name,
        ).first()
        if parent:
            subsystems[(parent.system_code, item.subsystem_code)] = item

    for row in planned["systems"]:
        item = CommissioningSystem(
            company_name=project.company_name, project_id=project.id,
            system_code=row["system_code"], name=row["name"],
            description=row["description"], p_and_id_ref=row["p_and_id_ref"],
            weight_percent=row["weight_percent"],
        )
        db.session.add(item)
        db.session.flush()
        systems[item.system_code] = item
        add_audit_event(project.company_name, "CommissioningSystem", item.id,
                        "SYSTEM_IMPORTED", after={"system_code": item.system_code})

    for row in planned["subsystems"]:
        parent = systems[row["system_code"]]
        item = CommissioningSubsystem(
            company_name=project.company_name, system_id=parent.id,
            subsystem_code=row["subsystem_code"], name=row["name"],
            description=row["description"], weight_percent=row["weight_percent"],
            mc_target_date=row["mc_target_date"], rf_target_date=row["rf_target_date"],
        )
        db.session.add(item)
        db.session.flush()
        subsystems[(row["system_code"], item.subsystem_code)] = item
        add_audit_event(project.company_name, "CommissioningSubsystem", item.id,
                        "SUBSYSTEM_IMPORTED", after={"subsystem_code": item.subsystem_code,
                                                      "system_code": row["system_code"]})

    equipment_by_tag = {
        item.tag_number: item for item in CommissioningEquipment.query.filter_by(
            company_name=project.company_name, project_id=project.id,
        ).all()
    }
    for row in planned["equipment"]:
        parent = subsystems[(row["system_code"], row["subsystem_code"])]
        item = CommissioningEquipment(
            company_name=project.company_name, project_id=project.id,
            subsystem_id=parent.id, tag_number=row["tag_number"],
            equipment_type=row["equipment_type"], description=row["description"],
            manufacturer=row["manufacturer"], model_number=row["model_number"],
            serial_no=row["serial_no"], status=row["status"],
        )
        db.session.add(item)
        db.session.flush()
        equipment_by_tag[item.tag_number] = item
        add_audit_event(project.company_name, "CommissioningEquipment", item.id,
                        "EQUIPMENT_IMPORTED", after={"tag_number": item.tag_number})

    for row in planned["tasks"]:
        parent_system = systems[row["system_code"]]
        parent_subsystem = subsystems[(row["system_code"], row["subsystem_code"])]
        equipment_item = equipment_by_tag.get(row["equipment_tag"]) if row["equipment_tag"] else None
        item = CommissioningTask(
            company_name=project.company_name, project_id=project.id,
            system_id=parent_system.id, subsystem_id=parent_subsystem.id,
            equipment_id=equipment_item.id if equipment_item else None,
            task_number=row["task_number"], title=row["title"],
            description=row["description"], activity_type=CommissioningTaskType(row["activity_type"]),
            discipline=row["discipline"], progress_stage=row["progress_stage"] or None,
            progress_substage=row["progress_substage"] or None,
            assigned_group=row["assigned_group"] or None,
            estimated_man_hours=row["estimated_man_hours"],
            planned_start_date=row["planned_start_date"],
            planned_finish_date=row["planned_finish_date"],
            status=CommissioningTaskStatus.NOT_STARTED, created_by_id=current_user.id,
        )
        db.session.add(item)
        db.session.flush()
        add_audit_event(project.company_name, "CommissioningTask", item.id,
                        "TASK_IMPORTED", after={"task_number": item.task_number,
                                                "activity_type": item.activity_type.value})
    db.session.commit()


@commissioning_bp.get("/projects/<int:project_id>/engineering-data")
@login_required
def engineering_data_exchange(project_id):
    if not has_permission(project_id, "structure.manage"):
        abort(403)
    project = get_project(project_id)
    return render_template("commissioning/engineering_data_exchange.html", project=project)


@commissioning_bp.get("/projects/<int:project_id>/engineering-data/template")
@login_required
def download_engineering_template(project_id):
    if not has_permission(project_id, "structure.manage"):
        abort(403)
    project = get_project(project_id)
    workbook = _new_workbook()
    _style_workbook(workbook)
    return send_file(
        _workbook_bytes(workbook),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name=f"{project.project_code}-engineering-import-template.xlsx",
    )


@commissioning_bp.get("/projects/<int:project_id>/engineering-data/export")
@login_required
def export_engineering_registers(project_id):
    if not any(has_permission(project_id, permission) for permission in (
        "structure.view", "tasks.view", "project.manage",
    )):
        abort(403)
    project = get_project(project_id)
    workbook = _export_workbook(project)
    safe_code = re.sub(r"[^A-Za-z0-9_-]+", "-", project.project_code).strip("-") or "project"
    return send_file(
        workbook, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name=f"{safe_code}-engineering-registers.xlsx",
    )


@commissioning_bp.route("/projects/<int:project_id>/engineering-data/import", methods=["GET", "POST"])
@login_required
def import_engineering_registers(project_id):
    if not has_permission(project_id, "structure.manage"):
        abort(403)
    project = get_project(project_id)
    if request.method == "GET":
        return redirect(url_for("commissioning.engineering_data_exchange", project_id=project.id))

    upload = request.files.get("workbook")
    if upload is None or not upload.filename:
        abort(400, description="Choose an .xlsx workbook.")
    if Path(upload.filename).suffix.lower() != ".xlsx":
        abort(400, description="Only .xlsx workbooks are supported.")
    raw = upload.stream.read(MAX_WORKBOOK_BYTES + 1)
    if len(raw) > MAX_WORKBOOK_BYTES:
        abort(413, description="Workbook exceeds the 5 MB import limit.")
    if not raw:
        abort(400, description="Workbook is empty.")

    errors = []
    try:
        workbook = load_workbook(BytesIO(raw), read_only=True, data_only=True)
    except Exception:
        abort(400, description="The uploaded file is not a valid .xlsx workbook.")
    parsed = _read_rows(workbook, errors)
    workbook.close()
    planned, validation_errors = _validate_import(project, parsed)
    errors.extend(validation_errors)
    summary = {name: len(rows) for name, rows in planned.items()}
    action = request.form.get("action", "validate")
    if errors:
        return render_template(
            "commissioning/engineering_data_exchange.html", project=project,
            errors=errors, summary=summary, imported=False, dry_run=True,
        ), 400
    if action != "import":
        return render_template(
            "commissioning/engineering_data_exchange.html", project=project,
            errors=[], summary=summary, imported=False, dry_run=True,
        )
    if planned["tasks"] and not has_permission(project.id, "tasks.create"):
        abort(403)
    try:
        _import_workbook(project, planned)
    except IntegrityError:
        db.session.rollback()
        errors.append({"sheet": "Database", "row": "—", "field": "integrity",
                       "message": "A database constraint rejected the import. No rows were committed; check duplicate or conflicting identifiers."})
        return render_template(
            "commissioning/engineering_data_exchange.html", project=project,
            errors=errors, summary=summary, imported=False, dry_run=False,
        ), 409
    flash("Engineering registers imported successfully. Existing records were not overwritten.", "success")
    return redirect(url_for("commissioning.engineering_data_exchange", project_id=project.id))
