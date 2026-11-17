# OPERA Testing Report

**Report date:** 17 November 2026  
**Merged release commit:** d4ea938db5f2763508934a03c2f27298815af8f4  
**Feature branch head validated:** 0e16012f208468d5ef0ebb23d9c7dace913d5e51

## GitHub Actions evidence

- Feature branch run [44044731563](https://github.com/Tahmoures54/opera/actions/runs/44044731563): **success**.
- Post-merge main run [44045305154](https://github.com/Tahmoures54/opera/actions/runs/44045305154): **success**.

### Quality job
- Ruff: passed.
- Mypy: passed.
- Migration/build-boundary checks: passed.
- Operational shell-script validation: passed.
- Core pytest with coverage gate: passed.
- OPERA commissioning tests and coverage gate: passed.
- Bandit: passed.
- pip-audit: passed.

### PostgreSQL integration job
- Empty-database production migrations: passed.
- Concurrent TOTP recovery replay test: passed.
- Forward upgrade from previous schema revision: passed.
- PostgreSQL backup and isolated restore: passed.
- Application readiness and public-funnel smoke tests: passed.

### Docker job
- Production Compose validation: passed.
- Nginx configuration validation: passed.
- Production image build: passed.
- Trivy vulnerability scan: passed.
- Trivy report upload: passed.

## Task Register coverage added

- Task model registration and project/system/subsystem/equipment association.
- Optional task-to-CheckSheet association constrained to the same project hierarchy.
- Non-negative estimated/spent man-hour database constraints.
- Task role permissions.
- Task Register GET/POST, search and activity filtering.
- Task creation audit event and company boundary checks.

## Production status — separate from CI

The Vercel production deployment was **not** updated by this merge at the time of this report. The latest observed Production deployment remained READY on commit 7cea63326e767e29d3a206e7a14dfb11054c93a9. The Vercel Git status reported a Build Rate Limit page, and no deployment for the merged commit was found.

The new Alembic migration passed on CI PostgreSQL, but it has **not** been applied to the live production database. Do not treat CI migration success as evidence that the live database schema was changed.

## Remaining verification

- Apply migration 20261117_0020 to Production only after a production database backup and a documented rollback plan.
- Re-deploy the exact main commit after Vercel build availability is restored.
- Confirm the production deployment commit matches main.
- Run authenticated production Task Register smoke tests after the migration.
- Verify durable evidence storage on Vercel; the current local filesystem adapter is not durable serverless storage.
- Browser-based responsive verification remains outstanding.

## Conclusion

The merged source passed the full GitHub Actions quality, PostgreSQL integration, backup/restore and Docker security/build pipeline. Production readiness is still blocked by the Vercel deployment rate limit and the unapplied production migration.
