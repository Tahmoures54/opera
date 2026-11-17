# OPERA Subsystem Dossier Exports

## Available outputs

From a subsystem's Completion Dossier page:

- PDF — printable summary of the current equipment/tag register, engineering document revisions, Check Sheets, Punch items, tasks, Preservation plans, certificates, evidence index and dossier/readiness checks.
- ZIP + Evidence — the PDF, a JSON manifest and the linked evidence files for the included current records.

The ZIP builder checks each stored file against its database SHA-256 checksum. A missing object or checksum mismatch aborts the package with HTTP 409; the system does not silently omit evidence. The default declared-evidence limit is 100 MiB, configurable through OPERA_DOSSIER_EXPORT_MAX_BYTES.

## Scope and limitations

Every generated file is a point-in-time UNCONTROLLED_WORKING_EXPORT. It is not a controlled or approved contractual dossier and does not issue MC/RFC certificates. The current export does not persist a dossier revision record and does not provide review, approval, rejection or formal issue workflow. The dossier index/readiness results remain a current-state assessment.

Use the approved project completion procedure and the formal MC/RFC/RFSU/Operations Acceptance workflow for contractual handover. Do not treat a PDF/ZIP download as approval or custody transfer.
