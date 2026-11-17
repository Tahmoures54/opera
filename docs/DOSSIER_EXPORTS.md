# OPERA Subsystem Dossier Exports

## Available outputs

From a subsystem's Completion Dossier page:

- PDF — printable summary of the current equipment/tag register, engineering document revisions, Check Sheets, Punch items, tasks, Preservation plans, certificates, evidence index and dossier/readiness checks.
- ZIP + Evidence — the PDF, a JSON manifest and the linked evidence files for the included current records.

The ZIP builder checks each stored file against its database SHA-256 checksum. A missing object or checksum mismatch aborts the package with HTTP 409; the system does not silently omit evidence. The default declared-evidence limit is 100 MiB, configurable through OPERA_DOSSIER_EXPORT_MAX_BYTES.

## Scope and limitations

The legacy subsystem PDF/ZIP export routes remain point-in-time UNCONTROLLED_WORKING_EXPORT files. They are not controlled or approved contractual dossiers and do not issue MC/RFC certificates.

The controlled dossier register creates immutable, revision-numbered snapshots. Its workflow is DRAFT → IN_REVIEW → APPROVED or REJECTED → ISSUED. The author cannot review their own revision; a separate Commissioning Manager issues an approved revision. Approval is blocked when captured dossier readiness checks fail or referenced evidence is unavailable/checksum-invalid. Issued PDF/ZIP exports use the stored snapshot rather than current live records. The ZIP contains a manifest and verifies each referenced evidence file against its stored SHA-256 checksum.

Issued dossier revisions and review decisions are append-only. A new revision is required for changes. This workflow provides OPERA record control, not a qualified electronic signature or automatic contractual acceptance. Project procedures and Operations acceptance remain authoritative.

Use the approved project completion procedure and the formal MC/RFC/RFSU/Operations Acceptance workflow for contractual handover. Do not treat a PDF/ZIP download as approval or custody transfer.
