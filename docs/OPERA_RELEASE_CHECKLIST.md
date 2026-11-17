# OPERA Release Readiness Checklist

**Code baseline:** `3d2095b0ff3e006f607429f95c0b531f83379f94` (merge commit for PR #39)  
**CI run:** [44084364501](https://github.com/Tahmoures54/opera/actions/runs/44084364501) — PR head `417654cf6a2db1ac8ff94c3a45426307ab8fdcd9`; all quality-job steps passed.

## Repository and CI
- [x] Main contains Task, Check Sheet, Punch, document-control, engineering exchange, dossier index, MC/RFC, readiness, Preservation and S3-compatible evidence-storage increments.
- [x] `quality`, `integration` and `docker` checks passed on the earlier baseline `ca37db49224160628e9fb28d3b7d51930acc099f`.
- [x] PR #39 `quality` job passed on head commit `417654cf6a2db1ac8ff94c3a45426307ab8fdcd9` (Ruff, Mypy, migration/script checks, core Pytest, commissioning Pytest, Bandit and pip-audit).
- [ ] Reconcile and remove obsolete remote feature branches after confirming merged ancestry; retain any branch with unmerged work.
- [ ] Confirm no stale or duplicate pull requests remain open.

## Production deployment and evidence controls
- [ ] Configure production secrets and PostgreSQL connection settings.
- [ ] Rehearse the current Alembic head upgrade on a production-like staging database.
- [ ] Take and verify a production database backup before migration.
- [ ] Configure `OPERA_STORAGE_BACKEND=s3`, bucket, region and (if needed) endpoint/credentials for durable private evidence storage; local uploads are blocked on serverless runtimes.
- [ ] Migrate existing local evidence objects to the bucket and verify every stored SHA-256 checksum.
- [ ] Verify object access controls, encryption, retention, malware scanning and off-host backup.
- [ ] Perform paired database/evidence backup and restore rehearsal.
- [ ] Verify deployment health, HTTPS, logging, monitoring and rollback procedure. The Vercel check on the merge commit currently reports `build-rate-limit`; deployment success is not verified.

## Project acceptance
- [ ] Approve systemization, activity taxonomy, Check Sheet templates and the configured MC/RFC/RFSU readiness policy.
- [ ] Configure preservation plans from approved OEM/project procedures and verify the inspection/corrective-action workflow.
- [ ] Approve the required Check Sheet/Test Sheet template revisions and verify item-level mandatory, witness, unit and acceptance rules.
- [ ] Approve Punch category meanings, Hold/Witness procedures, waiver rules and certificate signatory matrix.
- [ ] Run a realistic end-to-end scenario using separate contractor, executor, QC, client and Operations accounts.
- [ ] Verify direct HTTP requests cannot bypass role checks or readiness gates.
- [ ] Configure and approve the project dossier index (document types, disciplines, minimum counts, approval and evidence requirements).
- [ ] Verify certificate and dossier evidence against the approved project completion procedure.
- [ ] Verify generated dossier PDF/ZIP package and revision/approval controls when that module is delivered.
- [ ] Obtain project owner / Operations acceptance.

A successful CI run is necessary but is not evidence of production deployment, durable evidence retention or project acceptance.
