# OPERA Changelog

All notable OPERA product changes are recorded here. OPERA is an independent commissioning and start-up product. It reuses shared infrastructure from the original MaterialHub codebase, but MaterialHub is not the product identity.

## [Unreleased] — 2026-11-19

### Readiness (MC)
- Mechanical Completion requires registered Pre-Comm A and Pre-Comm B check sheets by default.
- Project-configurable MC gates for incomplete task activity types, dossier document rules and equipment statuses.
- Added mechanical check sheet types: HYDROTEST, LEAK_TEST, FLUSH_BLOW, MEGGER, CALIBRATION (migration 20261119_0036, not yet verified against a database).
- Corrected readiness documentation that described required-sheet configuration as future work.
- Known limitation: the new MC gates and migration have not been run in CI; validate before release.

## [Unreleased] — 2026-11-16

### Product identity and architecture
- Established OPERA as a standalone product for EPC, industrial and construction commissioning projects.
- Retained the inherited Flask application factory, SQLAlchemy/Alembic database, authentication, TOTP, CSRF and tenant-security foundation.
- Reused the existing company boundary as the OPERA tenant boundary; no duplicate tenant or authentication system was introduced.
- Added OPERA-specific navigation, Persian landing page, help content and release documentation.

### Commissioning workflows
- Added project-scoped membership and OPERA roles, independent of inherited account roles.
- Added Project → System → Subsystem → Equipment structure.
- Added check-sheet preparation, issue/rejection, item results, independent QC verification, contractor/client sign-off and immutable revisions.
- Added Punch List assignment, controlled status transitions, independent verification, waiver history and MC A/B gates.
- Added Witness, Hold and Review point scheduling, notification, attendance and release.
- Added MC, RF, RFSU, operations acceptance/rejection and progress snapshots.
- Added OPERA audit evidence and tenant-scoped authorization checks.

### Production and security
- Added PostgreSQL production configuration, Docker Compose deployment, Gunicorn, Nginx TLS, Redis-backed rate limiting, health checks and operational scripts.
- Added PostgreSQL backup and isolated restore procedures and a production launch checklist.
- Removed the legacy shared-password demo seeder; production startup never seeds demo accounts.
- Added an OPERA production image that omits Python's optional SQLite module and SQLite runtime package; SQLite remains available for local development and tests.
- Upgraded vulnerable Pillow and OpenTelemetry dependencies.
- Added CI gates for Ruff, Mypy, pytest with coverage, Bandit, pip-audit, PostgreSQL migrations and recovery tests, backup/restore, production smoke tests, Docker build and Trivy scanning.

### Known release limitations
- Electronic sign-off is an authenticated, auditable acknowledgement, not a qualified PKI signature.
- Evidence attachment upload/download screens and production object storage are not included.
- A real staging acceptance test with separate contractor, QC, client and operations accounts is required before go-live.
- Production deployment still requires operator-provided domain, TLS certificate, database password, Flask secret, SMTP (if used), monitoring and a verified backup policy.
