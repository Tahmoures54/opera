# OPERA Release Readiness Checklist

**Code baseline:** main merge commit `56bcc9de1a5cec81d4aea68e3ad8d9d8f11e9211` (PR #43).  
**CI run:** [44091665590](https://github.com/Tahmoures54/opera/actions/runs/44091665590) — quality, PostgreSQL integration and Docker jobs passed on the final PR head.

## Repository and CI
- [x] Main contains Task, revision-controlled Check Sheet templates, Punch, document-control, engineering exchange, dossier index, controlled dossier revisions, MC/RFC, readiness, Preservation and S3-compatible evidence-storage increments.
- [x] PR #43 controlled dossier lifecycle merged after all CI checks passed.
- [x] `quality`, `integration` and `docker` checks passed on the earlier baseline `ca37db49224160628e9fb28d3b7d51930acc099f`.
- [x] PR #39 `quality`, `integration` and `docker` jobs passed on head commit `417654cf6a2db1ac8ff94c3a45426307ab8fdcd9`.
- [x] PR #40 `quality`, `integration` and `docker` jobs passed on head commit `283a30c30c1f6bd5fe998636c56e38c70cb5e7e6`.
- [x] PR #42 `quality`, PostgreSQL `integration` and `docker` jobs passed on head commit `578a609392b538f27091f16e64ce9ef8e23b8161`.
- [x] PR #43 `quality`, PostgreSQL `integration` and `docker` jobs passed on final head commit `b2366a8b52fb3f1011caf179d5ae92a251b43559`.
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
- [ ] Approve Punch category meanings, Hold/Witness procedures, waiver rules and certificate signatory matrix.
- [ ] Run a realistic end-to-end scenario using separate contractor, executor, QC, client and Operations accounts.
- [ ] Verify direct HTTP requests cannot bypass role checks or readiness gates.
- [ ] Configure and approve the project dossier index (document types, disciplines, minimum counts, approval and evidence requirements).
- [ ] Verify certificate and dossier evidence against the approved project completion procedure.
- [x] Verify generated dossier PDF/ZIP package and checksum/missing-evidence controls in PR #40 automated tests.
- [ ] Exercise dossier draft, submit, independent review, rejection, approval, separate issue and issued PDF/ZIP exports with distinct project accounts.
- [ ] Verify an incomplete dossier cannot be approved and an issued snapshot cannot be modified.
- [ ] Verify issued dossier evidence against the configured storage backend and complete a backup/restore rehearsal.
- [ ] Verify Preservation report filters, due-status counts, tenant scope and spreadsheet-safe CSV export.
- [ ] Obtain project owner / Operations acceptance.

A successful CI run is necessary but is not evidence of production deployment, durable evidence retention or project acceptance.
