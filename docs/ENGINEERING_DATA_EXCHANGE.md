# OPERA Engineering Data Exchange

**Workbook contract:** `OPERA_ENGINEERING_DATA_EXCHANGE`, version `1`  
**Scope:** One OPERA project at a time.  
**Format:** XLSX only; maximum upload size 5 MB; maximum 5,000 data rows per worksheet.

This is an OPERA-owned engineering workbook. It is independently designed for OPERA and is not an official ICAPS template or a claim of exact ICAPS import compatibility.

## Safe import procedure

1. Download the template from the target project's **Engineering Data Exchange** page.
2. Keep the hidden `_OPERA_META` worksheet intact. Its format identifier, version and project code bind the workbook to the target project.
3. Fill the required worksheets and keep the exact column headers.
4. Upload the workbook and run **Validate workbook (dry run)**.
5. Resolve every row-level error. A failed dry run writes nothing.
6. Re-select the exact same workbook and confirm **Import validated records**. OPERA compares its SHA-256 digest with the successful dry run before writing.
7. The import creates Systems, Subsystems, Equipment and Tasks in dependency order inside one database transaction. Each created record receives an audit event.

Imports are create-only. Existing records, approved Check Sheets, document revisions and execution evidence are never overwritten. Duplicate identifiers are errors rather than implicit updates.

## Worksheets

### Systems

| Column | Required | Meaning |
|---|---:|---|
| `system_code` | Yes | Unique code within the project |
| `name` | Yes | System name |
| `description` | No | Description |
| `p_and_id_ref` | No | P&ID reference |
| `weight_percent` | No | 0–100; defaults to 0 |

### Subsystems

| Column | Required | Meaning |
|---|---:|---|
| `system_code` | Yes | Existing or same-workbook parent system |
| `subsystem_code` | Yes | Unique under its parent system |
| `name` | Yes | Subsystem name |
| `description` | No | Description |
| `weight_percent` | No | 0–100; defaults to 0 |
| `mc_target_date` | No | ISO date or Excel date |
| `rf_target_date` | No | ISO date or Excel date |

### Equipment

| Column | Required | Meaning |
|---|---:|---|
| `tag_number` | Yes | Unique project equipment tag |
| `system_code` | Yes | Parent system |
| `subsystem_code` | Yes | Parent subsystem under that system |
| `equipment_type` | Yes | Equipment type |
| `description` | No | Description |
| `manufacturer` | No | Manufacturer |
| `model_number` | No | Model |
| `serial_no` | No | Serial number |
| `status` | No | Defaults to `ACTIVE` |

### Tasks

| Column | Required | Meaning |
|---|---:|---|
| `task_number` | Yes | Unique within the company |
| `system_code` | Yes | Parent system |
| `subsystem_code` | Yes | Parent subsystem under that system |
| `equipment_tag` | No | Equipment in the same subsystem |
| `activity_type` | Yes | One of CCK, STS, PIP, PRC, FTS, OTS, PVP |
| `title` | Yes | Task title |
| `description` | No | Task description |
| `discipline` | Yes | Responsible discipline |
| `progress_stage` | No | Project-defined stage |
| `progress_substage` | No | Project-defined substage |
| `assigned_group` | No | Responsible work group |
| `estimated_man_hours` | No | Non-negative finite number; defaults to 0 |
| `planned_start_date` | No | ISO date or Excel date |
| `planned_finish_date` | No | Must not precede planned start |

Imported tasks start in `NOT_STARTED`. Execution status, actual dates, spent hours, predecessor links, check-sheet sign-offs and approvals are deliberately not importable through this engineering master-data workbook.

## Validation and protection

- References are resolved only inside the selected tenant and project.
- Task equipment references must point to equipment in the same system and subsystem.
- Duplicate system, subsystem, equipment and task identifiers are rejected.
- Formula cells are rejected; replace formulas with reviewed values.
- Negative or non-finite hours and out-of-range weights are rejected.
- Workbook project code and schema version must match.
- Import is committed atomically; a database failure rolls back the whole batch.
- Every imported entity receives an audit event.

## Export

The project export contains the same four worksheets and the hidden workbook metadata. It is a current-register export, not a backup of attachments or a replacement for the database backup process.
