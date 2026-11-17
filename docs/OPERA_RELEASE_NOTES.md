# OPERA Release Notes — Commissioning Implementation Baseline

**Baseline commit:** main merge commit `56bcc9de1a5cec81d4aea68e3ad8d9d8f11e9211` (PR #43).  
**Verification:** GitHub Actions run `44091665590`; `quality`, PostgreSQL `integration` and `docker` checks completed successfully on the final PR head.

## Implemented capabilities on main
- Standalone OPERA product identity and commissioning-focused navigation.
- Tenant-scoped project, System, Subsystem and Equipment/Tag structure.
- Commissioning Task Register with historical OPERCOM activity-code references, audited execution transitions and finish-to-start dependencies with cycle detection.
- Check Sheet issue/execution, item results, independent QC verification, two-party sign-off, rejection/rework and controlled immutable revisions.
- Punch List creation, assignment, corrective action, closure, audited reopening, history, verification and waiver evidence.
- Witness/Hold/Review point workflow and readiness blocking for unreleased Hold points.
- Controlled engineering Document Register with revision history, file evidence metadata, review and approval decisions.
- OPERA-owned XLSX engineering data exchange for Systems, Subsystems, Equipment and Tasks, including dry-run validation, SHA-256 workbook confirmation, atomic create-only import and audit.
- Subsystem completion dossier/readiness view consolidating documents, Check Sheets, Punch items, witness/hold points, equipment and tasks.
- Project-configurable dossier document index with discipline, minimum-count, approval and attachment-record rules, evaluated against current document revisions.
- Immutable MC and RFC certificates with issue-time evidence snapshots; separate RFSU gate and Operations Acceptance transition.
- Project-configurable readiness policy for Punch blockers, required Check Sheet types, Hold-point gates, Check Sheet presence and RFSU task completion; invalid policy fails closed and certificate snapshots retain the effective policy.
- Equipment Preservation plans with approved procedure references/revisions, user-supplied intervals and due dates, append-only inspection history, corrective-action workflow and evidence attachments.
- Scoped progress snapshots with Check Sheet and Task count/weight metrics and Punch counts.
- Project-scoped role authorization, tenant filters and append-only evidence/audit protections.

## Known limitations / production blockers
- Readiness rules are project-configurable for Punch categories, Check Sheet types, Hold-point gates and RFSU task completion. Project approval and a complete signatory/waiver authority matrix are still required.
- Controlled subsystem dossier revisions, independent review, separate issue authorization and issued PDF/ZIP exports are implemented. Project-specific section/authority matrices, Operations Acceptance linkage and staging acceptance remain outstanding.
- Revision-controlled Check Sheet/Test Sheet templates are implemented; advanced measurement capture, configurable result vocabularies, qualified e-signatures and generated blank form packs remain future work.
- An S3-compatible evidence-storage adapter is implemented and serverless local uploads fail closed. A real private bucket, provider-side retention/versioning and a successful paired database/object backup-restore rehearsal are still required before production evidence use.
- Electronic sign-off is an authenticated acknowledgement, not a qualified cryptographic signature.
- Preservation reminders, recurring scheduling, plan revision workflow, preservation templates and advanced compliance reporting remain future work. Daily work logs, full resource/capacity planning and expanded reporting also remain future work.
- No claim is made that OPERA's Excel contract, report formulas, permissions or forms exactly match a current ICAPS release.

## Release rule
Green CI validates the tested commit in CI. It does not replace staging migration rehearsal, production backup/restore, durable evidence storage, end-to-end multi-role acceptance or operational sign-off.


### Preservation compliance reporting

Added a project-level Preservation Compliance Report with due-status and equipment filters, plan/equipment register, latest inspection and corrective-action context, summary counts, and UTF-8 CSV export. Formula-like cell values are escaped to reduce spreadsheet formula-injection risk. The report does not invent technical preservation limits or calculate an unsupported compliance percentage.

### Controlled subsystem dossier lifecycle

Added immutable subsystem dossier revision snapshots with SHA-256 integrity metadata, DRAFT/IN_REVIEW/APPROVED/REJECTED/ISSUED workflow, append-only review decisions, author/reviewer/issuer separation, readiness and evidence checks before approval/issue, and controlled issued PDF/ZIP exports. Existing current-state PDF/ZIP routes remain explicitly uncontrolled working exports.

### Check Sheet template engine

Added project-scoped revision-controlled Check Sheet/Test Sheet templates, approved-template immutability, revision snapshots on instantiated sheets, mandatory/optional inspection items, item-level acceptance criteria and units, and sign-off gates for independent QC verification and witness release.
