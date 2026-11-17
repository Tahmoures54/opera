# OPERA Production Readiness Report

Repository: `Tahmoures54/opera`
Product: OPERA — Operations, Pre-commissioning & Commissioning Management

## Current product boundary

The OPERA runtime exposes shared authentication, help, marketing, health and commissioning workflows. The inherited MaterialHub procurement, warehouse, supplier, delivery, generic reporting, intelligence and role-workspace HTTP modules and their templates have been removed from the application source.

## Preserved platform services

- Flask application factory and WSGI entry point
- User authentication, password recovery, TOTP and session security
- CSRF, rate limiting, error handling and structured logging
- SQLAlchemy, Alembic, PostgreSQL and Vercel configuration
- Tenant/company scoping and project-scoped commissioning membership
- Commissioning project, system/subsystem, check sheet, punch, witness, handover, evidence and progress models

## Database safety

Historical MaterialHub-era model mappings and migration revisions remain in place as a compatibility measure. No historical migration was rewritten and no production table was dropped. Removing those mappings or dropping tables requires a verified inventory of production data, backup validation and an explicit retention decision. Details are in `docs/LEGACY_DATA_COMPATIBILITY.md`.

## Validation performed in this cleanup

- Python compilation: passed.
- Pytest: 95 passed, 1 skipped.
- Legacy HTTP routes: regression tests assert 404 responses.
- Commissioning project access and workflow tests: retained and executed as part of the test suite.

## Not yet certified

- GitHub Actions on the cleanup branch has not yet been observed.
- A new Vercel deployment of this cleanup branch has not yet been created or tested.
- Production database upgrade and live data inventory have not been run.
- Docker/Trivy production image validation and PostgreSQL upgrade tests require the repository CI environment.

The latest production deployment observed before this cleanup was marked READY for commit `d6cd0c2`. That status does not certify this unmerged cleanup branch.
