# OPERA Document Templates and Data Contracts

## Status
This document records the current template strategy. The current ICAPS blank forms, field dictionaries and import/export annex were not supplied, so no OPERA output is represented as an official ICAPS form.

## Current data-bearing records
- Check Sheet and Check Sheet Item: sheet number, type, revision, title, system/subsystem/equipment links, expected/actual result, item status, witness flag, verification and sign-off.
- Punch Item: punch number, category, severity, subsystem/equipment/check-sheet links, description, owner, target date, clearance, verification and waiver evidence.
- Witness Point: type, notified party, scheduled time, attendance, result, remarks and release.
- Handover Package: package number, MC/RF certificate references and dates, issuer, Operations acceptance, rejection reason and document references.
- Commissioning Task: task number, activity code, title, discipline, project hierarchy, optional equipment/check-sheet link, stage/substage, group, man-hours and planned/actual dates.

## Template register

| Template | Current status | Required next step |
|---|---|---|
| Check Sheet | Implemented as interactive record; print-ready controlled template incomplete | Add approved reusable template catalog and PDF rendering |
| Inspection & Test Record | Partially represented by Check Sheet items | Add discipline-specific record definitions |
| Mechanical Completion Certificate | Milestone fields exist in handover model | Add controlled certificate artifact and readiness gate |
| System Completion Certificate | Not verified as separate artifact | Confirm contract terminology and implement if required |
| Commissioning Certificate | Partially represented by handover milestone | Add independent controlled certificate type |
| Punch List | Implemented as records and history | Add project-configurable form, export and closure matrix |
| Test Report | Partial | Add report model and PDF output |
| Inspection Report | Partial | Add report model and PDF output |
| Equipment Data Sheet | Equipment metadata exists | Add versioned field schema and import/export |
| System Handover Certificate | Partial | Add document artifact and approval sequence |
| Pre-Commissioning Procedure | Not implemented as controlled document type | Add Document Register first |
| Commissioning Procedure | Not implemented as controlled document type | Add Document Register first |
| Completion Dossier | Handover package foundation exists | Add indexed dossier and completeness validation |
| Turnover Package | Handover package foundation exists | Add document index, transmittal and acceptance |
| Daily / Weekly Progress Report | Not implemented as controlled report | Derive from audited execution events |
| Outstanding Items Report | Partial from Punch queries | Add filters, due-date aging and controlled export |
| System Status Report | Partial from project structure and progress snapshots | Add task/checksheet/punch evidence and approved formula |

## OPERA document identification (proposed)
Use a project-approved document number pattern. A suggested pattern is:

PROJECT-SYSTEM-SUBSYSTEM-DOCUMENT-TYPE-SEQUENCE

This is a proposal, not a confirmed ICAPS numbering rule. Revisions must be separate controlled records and must not overwrite an issued or signed artifact.

## Excel import/export contract (planned)
Each OPERA template will include:
- Template name and schema version.
- Project code and import batch identifier.
- Stable external reference keys.
- Required/optional field dictionary.
- Allowed enum values and date/number formats.
- Validation report with row number, field, rejected value and reason.
- Dry-run mode and explicit commit confirmation.
- No silent updates to signed or approved execution records.

## PDF generation (planned)
PDFs must include project identity, document number, revision, page numbering, generated timestamp, status, signatories and a clear “uncontrolled when printed” note where the contract requires it. Electronic acknowledgement in OPERA must not be described as a qualified digital signature unless an accredited signature provider is integrated.
