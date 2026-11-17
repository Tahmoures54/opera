# OPERA Architecture — Commissioning Product

## Product boundary
OPERA is an independently implemented project completion, pre-commissioning, commissioning and handover application. MaterialHub warehouse/material workflows are outside this product boundary. Shared authentication, account identity, tenant/company identity, database connectivity and deployment infrastructure are retained where required.

## Runtime architecture
- Backend: Flask application factory.
- Persistence: SQLAlchemy ORM.
- Schema evolution: Flask-Migrate / Alembic.
- Relational database: PostgreSQL in production; SQLite for local/test use where supported.
- Authentication: Flask-Login and the existing account security controls.
- UI: Jinja templates, Bootstrap-oriented markup, shared CSS and JavaScript.
- Deployment: Vercel/serverless configuration and Docker-based CI.
- Domain implementation: `models_commissioning.py`, `blueprints/commissioning/`, and `services/commissioning_*`.

## Implemented domain capabilities on main
- Project, System, Subsystem and Equipment/Tag registers.
- Commissioning Task Register with CCK, STS, PIP, PRC, FTS, OTS and PVP activity codes.
- Task execution state transitions, audit history and finish-to-start dependencies with cycle prevention.
- Check Sheet issue, execution results, independent QC verification, two-party sign-off, rejection/rework and controlled revisions.
- Punch lifecycle with corrective action, audited reopening, verification/waiver history and read-only history view.
- Witness / Hold / Review points and readiness blocking for unreleased Hold points.
- Controlled engineering Document Register with revision records, file evidence metadata, review and approval history.
- OPERA-owned XLSX engineering data exchange for Systems, Subsystems, Equipment and Tasks; dry-run validation, workbook SHA-256 confirmation, atomic create-only import and audit events.
- Subsystem dossier/readiness view aggregating current documents, Check Sheets, Punch items, Witness/Hold points, equipment and tasks.
- Project-configurable dossier document index with document type, discipline, minimum count, approval and attachment-record requirements; latest-revision matching and per-rule completeness results.
- Immutable MC and RFC certificate records with issue-time evidence snapshots; distinct RFSU readiness gate and Operations Acceptance transition.
- Project-configurable readiness policy for gate-specific Punch categories, required Check Sheet types, Hold-point blockers, Check Sheet presence and RFSU task completion. Invalid persisted policy fails all gates closed; issued certificate snapshots preserve the effective policy and gate-specific issues.
- Equipment Preservation plans with procedure/revision references, interval and due-date tracking, append-only inspection history, corrective-action state and evidence attachments.
- Progress snapshots with Check Sheet and Task count/weight metrics and Punch counts.
- Tenant-scoped project membership, server-side role permissions and append-only audit/evidence records.

## Readiness and handover
`services/commissioning_readiness.py` evaluates MC, RFC and RFSU readiness for a subsystem. Current defaults include required registered Check Sheets, open A/B Punch items and unreleased Hold points; RFC adds commissioning/functional-test Check Sheets; RFSU additionally requires tasks to be completed or cancelled. These are OPERA defaults, not universal ICAPS rules. Project-specific required-sheet selection, Punch blocking categories, signatory matrices and contractual acceptance rules require approved project configuration.

The implemented certificate types are MC and RFC. RFSU is a separate readiness/authorization transition; it is not an RFC certificate. Operations Acceptance is the final handover acceptance/rejection step.

## Data and security controls
1. Commissioning entities are scoped to the active company/tenant and project.
2. Cross-tenant/project references are rejected in service and route logic, with database constraints where implemented.
3. Project-role authorization is enforced server-side.
4. Workflow state changes and their audit events are committed together.
5. Signed Check Sheets, issued certificates, signatures, attachment metadata, review records and Punch history are protected from ordinary ORM mutation/deletion.
6. Progress is derived from persisted records; empty denominators do not produce fabricated completion.
7. The current evidence storage adapter writes to a local filesystem path. This is suitable only where the filesystem is persistent. It is not a durable Vercel/serverless evidence store.
8. Alembic migrations are additive and must be exercised against supported SQLite/PostgreSQL paths before release.

## Known gaps / next increments
- Reusable revision-controlled Check Sheet/Test Sheet template catalogue and controlled project instantiation.
- Further readiness-policy extensions: configurable witness/review point rules, waiver/signatory authority matrix and procedure-revision linkage.
- Full revision-controlled dossier PDF/ZIP package, dossier approval workflow and durable evidence-byte verification.
- Durable private object storage adapter, access controls, retention, malware scanning and paired database/object backup-restore.
- Automated reminders, recurring calendar planning, OEM interval library, preservation templates and advanced compliance reporting.
- Daily work logs, approved manpower capacity planning and vendor mobilization.
- Richer progress reporting and approved project/system roll-up formulas.
- Full document transmittals and configurable review cycles.
- Mobile/offline field execution and richer field evidence capture.
- Expanded audit coverage and consolidated workflow transition services.

## Non-goals
- Reintroducing MaterialHub warehouse, procurement, inventory or goods-receipt modules.
- Copying ICAPS proprietary source code, protected forms, artwork or branding.
- Claiming full ICAPS parity without current release-specific documentation and authorized representative project data.
