# OPERA Release Readiness Checklist

**Code baseline:** `ca37db49224160628e9fb28d3b7d51930acc099f`  
**CI run:** [44074781281](https://github.com/Tahmoures54/opera/actions/runs/44074781281)

## Repository and CI
- [x] Main contains the merged Task, Check Sheet, Punch, document-control, engineering exchange, dossier, MC/RFC and readiness increments.
- [x] `quality` check passed on the baseline commit.
- [x] `integration` check passed on the baseline commit.
- [x] `docker` check passed on the baseline commit.
- [ ] Reconcile and remove obsolete remote feature branches after confirming merged ancestry; retain any branch with unmerged work.
- [ ] Confirm no stale or duplicate pull requests remain open.

## Production deployment and evidence controls
- [ ] Configure production secrets and PostgreSQL connection settings.
- [ ] Rehearse the current Alembic head upgrade on a production-like staging database.
- [ ] Take and verify a production database backup before migration.
- [ ] Configure durable private object storage for evidence files; local filesystem storage is not suitable for Vercel/serverless persistence.
- [ ] Verify object access controls, encryption, retention, malware scanning and off-host backup.
- [ ] Perform paired database/evidence backup and restore rehearsal.
- [ ] Verify deployment health, HTTPS, logging, monitoring and rollback procedure.

## Project acceptance
- [ ] Approve systemization, activity taxonomy, Check Sheet templates and the configured MC/RFC/RFSU readiness policy.
- [ ] Configure preservation plans from approved OEM/project procedures and verify the inspection/corrective-action workflow.
- [ ] Approve Punch category meanings, Hold/Witness procedures, waiver rules and certificate signatory matrix.
- [ ] Run a realistic end-to-end scenario using separate contractor, executor, QC, client and Operations accounts.
- [ ] Verify direct HTTP requests cannot bypass role checks or readiness gates.
- [ ] Configure and approve the project dossier index (document types, disciplines, minimum counts, approval and evidence requirements).
- [ ] Verify certificate and dossier evidence against the approved project completion procedure.
- [ ] Verify generated dossier PDF/ZIP package and revision/approval controls when that module is delivered.
- [ ] Obtain project owner / Operations acceptance.

A successful CI run is necessary but is not evidence of production deployment, durable evidence retention or project acceptance.
