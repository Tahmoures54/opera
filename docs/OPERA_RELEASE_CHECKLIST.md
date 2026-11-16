# OPERA Release Readiness Checklist

This checklist distinguishes implemented workflows from production deployment evidence.

## Product and workflow
- [x] OPERA branding, product landing page and authenticated navigation
- [x] Project/system/subsystem structure foundation
- [x] Project-scoped membership and role permissions
- [x] Check-sheet issue, item results, independent QC verification, two-party sign-off and revisions
- [x] Punch creation, assignment, closure, verification and waiver history
- [x] Witness/Hold/Review scheduling, notification, attendance and release
- [x] MC, RF, RFSU and operations handover state gates
- [x] Project progress snapshots and audit evidence

## Automated verification
- [x] Ruff and Mypy pass on the first CI run
- [ ] Full pytest suite passes on the latest PR commit
- [ ] Bandit passes
- [ ] pip-audit passes with no unresolved high-risk advisories
- [ ] PostgreSQL migration/integration suite passes
- [ ] Docker build and Trivy scan pass

## Before production
- [ ] Review and merge the final PR
- [ ] Configure production secrets and PostgreSQL
- [ ] Take and verify a production database backup
- [ ] Apply migration 20261116_0019 in a staging environment
- [ ] Verify file/evidence storage and backup policy
- [ ] Run an end-to-end commissioning scenario with separate contractor, QC, client and operations accounts
- [ ] Verify HTTPS, readiness endpoint, logging and monitoring
- [ ] Obtain operational acceptance from the project owner

A successful CI run does not replace a staging acceptance test or a production backup/restore rehearsal.
