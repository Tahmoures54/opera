# MaterialHub — Enhancement Notes

## v1.1 — Product hardening

Operational fixes that make the existing MaterialHub modules actually usable end-to-end.

### Added
- Executive dashboard with live KPI cards for open MRs, pending POs, in-transit deliveries, low-stock items and open tenders.
- Role-aware workspace landing pages with priority and approval status.
- Fast-action navigation for requisitions, purchasing, warehouse, delivery, quality and suppliers.
- JSON API: `GET /api/overview` for dashboards and future mobile integrations.
- Health endpoint: `GET /health` for deployment monitoring.
- Security response headers and configurable session security.
- Production-oriented `.env.example` and a local `.env` with a generated secret.
- Responsive executive UI designed for desktop and tablet field-office use.

### Competitive direction
MaterialHub is positioned around a construction/EPC-specific material lifecycle: **Need → MR → Approval → Tender → PO → Delivery → QC → Warehouse → Availability**.

The product direction intentionally combines strengths seen in Procore Materials (supply-chain visibility, field receiving, inventory), Autodesk Forma/Construction Cloud (single source of truth and integrations), and Oracle Procurement (procure-to-pay, sourcing and supplier management), while keeping MaterialHub focused on material operations rather than becoming an overly broad enterprise suite.

## [Unreleased] — Production launch package (2026-09-20)

### Added
- `scripts/seed_demo.py` — safe multi-tenant demo data (users, projects, MR, PO, delivery, inventory, tender, bid, contact inquiry). Gated by `SEED_DEMO=1`.
- `scripts/prod_up.sh` — one-command helper for build / up / migrate / seed / status / logs.
- `docs/PRODUCTION_LAUNCH.md` — complete production go-live checklist and runbook.
- Expanded `.env.prod.example` with Redis rate-limit, cookie and optional OTEL settings.
- README section pointing to production launch docs.

### Notes
- Demo accounts use password `Demo@MaterialHub2026!` and pre-confirmed TOTP for convenience. Rotate before real users.
- Seed refuses to run if users already exist unless `--force` is passed.


## [Unreleased] - 2026-11-16

### Added
- Introduced the OPERA commissioning foundation with 16 tenant-scoped SQLAlchemy models, project-scoped memberships, audit/signature/attachment records, and signed-off check-sheet immutability guards.
- Added the initial OPERA project, system, and subsystem CRUD workspace under `/commissioning/`, reusing MaterialHub authentication, CSRF, database, and design system.
- Added Alembic revision `20261116_0019` for the OPERA foundation tables without altering existing MaterialHub tables.
- Added model tests for tenant-local uniqueness, hierarchy metadata, memberships, Punch records, and signed-off item immutability.
- Added tenant-scoped, atomic CheckSheet and Punch number allocation using MaterialHub’s existing `document_sequence` table.
- Added an explicitly gated OPERA demo seed script that requires an existing same-company user and creates the agreed 1-system, 2-subsystem, 3-equipment, 5-checksheet, 8-punch dataset.
