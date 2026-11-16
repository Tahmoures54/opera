# OPERA Release Notes — Productization Build

## Included in this build
- Standalone OPERA product identity, Persian landing page and help center.
- Project-scoped roles and organization-tenant isolation.
- Check-sheet lifecycle: draft, issue, item results, independent QC verification, client/contractor sign-off, rejection and revision.
- Punch lifecycle: raise, assign, progress, close, verify and waiver with append-only history.
- Witness/Hold/Review point lifecycle: plan, notify, attend and release.
- Handover lifecycle: MC, RF, RFSU, operations acceptance or rejection.
- Progress snapshots and audit evidence.

## Known limitations before production
- Electronic sign-off is a logged authenticated acknowledgement, not a PKI-based qualified signature.
- Evidence attachment upload/download screens and a production object-storage backend are not included in this build.
- Import/export templates, mobile/offline client, external scheduling integrations and configurable workflow templates remain future work.
- A real project acceptance test with separate contractor, QC, client and operations accounts is still required.
- Production migration, backup/restore rehearsal, deployment secrets and HTTPS configuration must be completed in the target environment.

## Release rule
Do not promote this build to production until the latest commit has a fully successful CI run and the staging acceptance checklist is signed off.
