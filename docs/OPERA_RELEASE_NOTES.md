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
- The production image is PostgreSQL-only and omits Python's optional SQLite runtime; SQLite remains available for local development and tests.
- Production migration, backup/restore rehearsal, deployment secrets and HTTPS configuration must be completed in the target environment.

## Release rule
Do not promote this build to production until the latest commit has a fully successful CI run and the staging acceptance checklist is signed off.


## Evidence storage and deployment hardening

- Added private tenant-scoped evidence upload/download for check sheets, Punch items and handover packages.
- Restricted uploads to PDF, PNG, JPG/JPEG, TXT and CSV with content-signature checks, bounded size, random storage keys and SHA-256 checksums.
- Added server-side project permission checks, private no-store downloads, append-only attachment metadata and immutable evidence after final sign-off/verification/acceptance.
- Added a persistent Docker evidence volume and paired database/evidence backup and evidence restore helpers.
- Removed the Vercel build-time database migration hook. Vercel build jobs must not mutate production database schema.
