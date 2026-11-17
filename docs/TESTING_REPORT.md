# OPERA Testing Report

**Report date:** 17 November 2026  
**Scope:** Source review and feature-branch implementation record. This report is not a declaration that the new feature has passed CI; CI must be checked for the final branch head.

## Baseline evidence
- Main CI run 44042583348 completed successfully for commit ca0579c8948c5e6a1ba2daa3de1ee9a5b5a835c8.
- Existing test modules include commissioning access, models, numbering and workflows.
- Existing CI includes Ruff, Mypy, pytest, PostgreSQL migration/integration, backup/restore, Docker build, Trivy, Bandit and pip-audit.

## Feature branch test additions
- Task model registration in SQLAlchemy metadata.
- Task hierarchy association with project/system/subsystem/equipment.
- Negative man-hour database constraint.
- Task permissions for project roles.

## Pending verification
- CI on the final feature branch head.
- Alembic forward migration on PostgreSQL from the previous production revision.
- Tenant-isolation test for task and optional check-sheet associations.
- Route-level authorization and input-validation tests.
- Browser responsive verification for the Task Register.
- Durable evidence storage and production smoke tests.

## Known test limitation
SQLite create_all tests validate model constraints but do not replace the PostgreSQL migration test. No production data migration was run by this feature branch.
