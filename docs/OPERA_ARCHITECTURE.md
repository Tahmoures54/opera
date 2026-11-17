# OPERA Architecture — Commissioning Product

## Product boundary

OPERA is a project-scoped Project Completion, Pre-commissioning and Commissioning application. MaterialHub warehouse/material workflows are outside this product boundary. Shared authentication, user identity, tenant/company identity, database connectivity and deployment infrastructure are retained only where still required.

## Current architecture observed

- Backend: Flask application factory.
- Persistence: SQLAlchemy ORM.
- Schema evolution: Flask-Migrate / Alembic.
- Relational database: PostgreSQL in production; SQLite supported for local/test use.
- Authentication: Flask-Login with existing account security controls.
- UI: Jinja templates, Bootstrap-oriented markup, shared CSS and JavaScript.
- Deployment: Vercel/serverless configuration and Docker-based CI.
- Domain package: `models_commissioning.py`, `blueprints/commissioning/`, `services/commissioning_*`.

## Current domain model

Existing model families observed:
- Project, System, Subsystem, Equipment.
- Check Sheet, Check Sheet Item, Check Sheet Revision.
- Punch Item and Punch History.
- Witness Point.
- Handover Package.
- Progress Snapshot.
- Audit Log, Attachment, Signature and Project Membership.

New task-register branch adds:
- Commissioning Task with project/system/subsystem/equipment references.
- Activity taxonomy: CCK, STS, PIP, PRC, FTS, OTS and PVP, based on the historical project ICAPS manual evidence.
- Discipline, progress stage/substage, assigned group, man-hour estimates/actuals, planned/actual dates and task status.

## Target relationship model

```text
Company / Tenant
  └── Project
       ├── System
       │    └── Subsystem
       │         ├── Equipment / Tag
       │         ├── Commissioning Tasks
       │         ├── Check Sheets
       │         ├── Punch Items
       │         └── Handover / Dossier
       ├── Project Memberships / Roles
       ├── Witness & Hold Points
       ├── Documents / Revisions (planned)
       └── Progress Snapshots (derived from approved source records)
```

## Architectural controls

1. Every commissioning entity is tenant-scoped.
2. Cross-tenant and cross-project references are rejected at query and database-constraint levels where possible.
3. Role checks are project-scoped; company-level admin status does not remove tenant filtering.
4. State changes must be audited in the same database transaction.
5. Signed/approved records must not be silently overwritten; revisions or controlled reopen events are required.
6. Progress is derived from persisted source records and approved weights; no demo or synthetic progress.
7. Attachments must use durable object storage in serverless production. The current local filesystem adapter is suitable only for persistent local/container storage, not as the final Vercel evidence store.
8. Alembic migrations must be additive and reversible where practical. Destructive schema retirement requires an explicit backup and empty-data verification.

## Next architectural increments

- Normalize task-to-discipline and task-to-document associations if project requirements confirm many-to-many relationships.
- Introduce a configurable progress sequence and predecessor/dependency model.
- Add a Document Register and controlled document revision/transmittal model.
- Add a reusable template catalog for Check Sheets and test procedures.
- Add a certificate/readiness engine that evaluates required evidence and unresolved punch constraints.
- Introduce an object-storage interface (local adapter for development; durable S3-compatible or Vercel-supported provider in production).
- Centralize state transition services so routes cannot bypass workflow invariants.

## Non-goals

- Reintroducing MaterialHub warehouse, procurement, inventory or goods-receipt modules.
- Copying ICAPS proprietary source code, protected form artwork or branding.
- Claiming full ICAPS parity without a current release-specific manual and representative authorized project data.
