# OPERA — Phase 1 Foundation

OPERA is an independently implemented commissioning and start-up workspace that extends MaterialHub without replacing its procurement, warehouse, quality, or reporting modules.

## Architecture decisions

- Tenant boundary: the existing `User.company_name` value is reused as `company_name` on every OPERA table. No second tenant registry is introduced.
- Identity: existing MaterialHub users, sessions, password verification, and TOTP are reused.
- Authorization: OPERA roles are project-scoped `CommissioningMembership` records. They do not change the legacy `User.access_level` enum or legacy workspace routing.
- Check-sheet revision policy: a signed-off check sheet and its items are immutable through ORM flush operations. Corrections are represented by a new check sheet revision.
- Database: revision `20261116_0019` creates only the 16 OPERA tables and is chained after `20261017_0018`.

## Initial routes

- `GET /commissioning/` — tenant-scoped project dashboard
- `GET|POST /commissioning/projects/new` — create a project and assign its creator as project commissioning manager
- `GET /commissioning/projects/<project_id>` — project/system/subsystem structure
- `GET|POST /commissioning/projects/<project_id>/systems/new` — create a system
- `GET|POST /commissioning/systems/<system_id>/subsystems/new` — create a subsystem
- `GET|POST /commissioning/projects/<project_id>/edit` — update project metadata
- `GET|POST /commissioning/systems/<system_id>/edit` — update system metadata
- `GET|POST /commissioning/subsystems/<subsystem_id>/edit` — update subsystem metadata
- `POST .../archive` — controlled archival when no dependent records exist

All state-changing browser forms use the application's global Flask-WTF CSRF protection.

## OPERA roles

| Role | Initial permission intent |
|---|---|
| commissioning_manager | Project and structure administration, all commissioning permissions |
| commissioning_engineer | Structure read, check-sheet create/fill, Punch raise |
| qc_inspector | Check-sheet read, Punch verification, witness attendance |
| client_representative | Read-heavy access and check-sheet sign-off |
| operations_lead | Read access and handover acceptance |
| viewer | Read-only project workspace |

The permission matrix is centralized in `services/commissioning_access.py`.

## Numbering

`services/commissioning_number_service.py` reuses MaterialHub's existing `document_sequence` table and `DocumentSequence.next_value()` atomic update. Keys remain within the existing 10-character limit and are scoped by `(key, company_name)`.

## Demo seed

The seed script requires an existing MaterialHub user and an explicit opt-in:

```bash
SEED_COMMISSIONING_DEMO=1 python scripts/seed_commissioning_demo.py \
  --company "Demo Contractor" --user-id 123
```

It refuses to overwrite an existing project with the same tenant and project code.

## Phase 1 scope boundaries

Check-sheet execution/sign-off workflows, Punch lifecycle operations, witness scheduling, handover acceptance, progress calculations, reports, imports/exports, and mobile APIs are not implemented in this foundation phase. The initial dashboard and structure CRUD are the available UI surface.

## Validation performed

- Python bytecode compilation and AST parsing.
- Jinja parsing for all new commissioning templates and the updated Persian user guide.
- SQLAlchemy/SQLite metadata smoke test: all 16 OPERA tables create successfully; cross-company hierarchy references are rejected with SQLite foreign-key enforcement enabled; signed-off item mutation is rejected.
- Alembic operation smoke test: upgrade creates all OPERA tables and downgrade removes only those tables.
- Full Flask pytest suite could not be run in the authoring environment because Flask/Flask-SQLAlchemy/Flask-Migrate are not installed and package installation is unavailable.
