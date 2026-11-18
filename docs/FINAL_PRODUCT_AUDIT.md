# OPERA Final Product Audit (Phase 1 baseline)

Scope: repository state at `main` commit `1fb354b` (shallow clone, read-only access).
Method: static inspection of code, migrations, CI workflow, deployment documents and
test inventory. **No tests, linters or Docker builds were executed in this audit**:
the audit environment has no Python dependencies installed and package installation
is blocked. Every "verified" status below therefore means verified by reading code,
not by running it. Items needing execution are marked `Production verification required`.

## 1. Status legend

- **Implemented and verified**: code and tests inspected; execution evidence still required for "verified by CI".
- **Implemented, insufficiently tested**: code present, test coverage not found or not inspected.
- **Partially implemented**: some workflow exists, required parts missing.
- **Not implemented**: no code path found.
- **Blocked by external evidence**: needs real provider, customer or deployment data.
- **Customer-configurable**: behaviour depends on project policy by design.
- **Production configuration outstanding**: deployment or infrastructure work remains.

## 2. Repository and migration state

| Item | Finding | Evidence |
|---|---|---|
| Default branch | `main` | `git branch` |
| Migration chain | Linear chain of 35 revision files from `20260901_0000` to `20261117_0033`. Single head, no branch. | `migrations/versions/*.py`, `down_revision` values |
| Open or unmerged branches | None visible in this shallow clone (only `main` fetched). PR list not accessible from this session. | `git branch -a` |
| Legacy MaterialHub schema | Still present in baseline and removal migration (`20261117_0019_remove_empty_materialhub_schema`). Compatibility tests exist. | `tests/test_legacy_schema_boundary.py` |

**Status: Implemented, insufficiently tested.** Migration chain is structurally consistent; PostgreSQL upgrade path is exercised in CI (`integration` job), not in this audit.

## 3. Documentation versus implementation

### 3.1 Deployment target: inconsistent documents (Partially implemented)

Three deployment stories exist and they disagree:

1. `docs/DEPLOYMENT_GUIDE.md` (section "Vercel") describes Vercel as the production target and states that local filesystem attachments are not durable on serverless platforms.
2. `docs/PRODUCTION_LAUNCH.md` and `docker-compose.production.yml` describe a Docker Compose stack with PostgreSQL 16, Nginx TLS and Docker secrets.
3. `vercel.json` is an empty object `{}`. CI asserts that no `buildCommand` exists, which is consistent with the rule not to run migrations at build time, but the file provides no deployment configuration.

Additional mismatch: `services/commissioning_storage.py` implements an **S3 backend** (`_s3_client`, `store_commissioning_upload`, `read_commissioning_upload`), yet `DEPLOYMENT_GUIDE.md` says the implementation is local filesystem only. The S3 path is not verified against a real provider (see §6).

**Required action**: one authoritative deployment guide. Proposed: Docker Compose on a private host as production, and remove or clearly mark the Vercel guidance as unsupported.

### 3.2 README claims (checked)

| README claim | Code evidence | Status |
|---|---|---|
| Project → System → Subsystem → Equipment hierarchy | `models_commissioning.py` (1173 lines) | Implemented, insufficiently tested (structure tests unverified) |
| Task Register with CCK / STS / PIP / PRC / FTS / OTS / PVP codes | Referenced in `models_commissioning.py` and `workflow.py`; activity-code catalogue configurability not verified | Partially implemented (catalogue configurability not confirmed) |
| Check sheets with independent QC, two-party sign-off, immutability after sign-off | `workflow.py` (2787 lines); revision model in `models_commissioning.py` | Implemented, needs execution-level verification |
| Punch A/B/C/D | `PunchCategory` enum (`models_commissioning.py` line 84) fixes the category set. Gate blocking is already project-configurable: `punch_blocking_categories` per gate in `services/commissioning_readiness_policy.py`, applied in `blueprints/commissioning/workflow.py` (`open_critical`). Category labels and meanings are not configurable. | **Partially implemented**: blocking rules configurable (tested); category set and meanings fixed |
| Witness / Hold / Review points | `WitnessPoint`, `WitnessStatus`, `transition_witness` in `workflow.py` (line 1117). Release requires `witness.manage` permission and a non-empty release note. | Implemented, insufficiently tested |
| Hold point blocks readiness | `services/commissioning_readiness.py` `_open_hold_points`, gate-specific via `hold_point_blocking_gates` policy | Implemented, policy-configurable |
| MC and RFC certificates, RFSU gate | `services/commissioning_readiness.py` (MC, RFC, RFSU evaluation); `RFC` certificate per `20261117_0026_rfc_certificate_lifecycle` | Implemented, insufficiently tested |
| Progress snapshots, audit, attachments | `20261117_0023_task_progress_snapshots`, `CommissioningAttachment` with SHA-256 checksum | Implemented, insufficiently tested |
| Tenant-scoped constraints and authorization | Queries filter by `company_name` (e.g. `transition_witness`); `tests/test_tenant_isolation.py` exists | Implemented, needs execution verification |
| "GitHub Actions runs Ruff, Mypy, pytest, Bandit, pip-audit, PostgreSQL integration checks, backup/restore, Docker scan" | Matches `.github/workflows/ci.yml` | Implemented in CI definition; **no run result inspected** |

### 3.3 Marketing and public pages

- Public routes exist: `/` (Home), `/demo`, `/pricing`, `/contact` (`blueprints/growth.py`), `/robots.txt`, `/sitemap.xml`, `/health/live`, `/health/ready` (CI smoke test).
- The repository `templates/Home.html` does **not** contain the fabricated metric tiles (`24 / 86 / 12 / 68%`) that appeared in a landing-page draft supplied in this session. The draft is not part of the repository. Keep it out of `main` unless every figure is replaced with real, verifiable data.

**Status: Implemented, insufficiently tested** (no responsive or funnel smoke test beyond the CI status-code checks).

### 3.4 Readiness terminology

`services/commissioning_readiness.py` documents "Independent implementation of MC, RFC and RFSU gates" and keeps `RF` as a deprecated compatibility alias. The brief requires logically distinct certificate types; this appears implemented but the policy file must be checked against `docs/READINESS_POLICY.md` in Phase 3.

## 4. Feature inventory against the brief

| Brief area | Current state | Classification |
|---|---|---|
| A. Project systemization (hierarchy, ownership, boundaries) | Hierarchy and models exist; ownership and completion-responsibility fields not verified | Partially implemented |
| B. Task management (dependencies, FS/SS/FF/SF, critical path) | Dependency migration `20261117_0022_commissioning_task_dependencies` exists; relationship types and critical-path logic not verified | Partially implemented; advanced dependency types not evidenced |
| C. Check Sheet / Test Sheet engine (numeric measurements, limits) | Migration `20261117_0032_checksheet_numeric_measurements` and template migration `20261117_0030` exist | Partially implemented; limit enforcement needs test verification |
| D. Punch management (categories, authority matrix, waiver) | Corrective-action migration `20261117_0025`. Gate blocking per category configurable and tested (`test_readiness_policy_changes_punch_blockers_per_gate`). Waiver is gated by the fixed `punch.verify` permission (`workflow.py` ~line 1023); no dedicated waiver test. No configurable authority matrix. | Partially implemented |
| E. Witness / Hold | Implemented as described in §3.2 | Implemented, insufficiently tested |
| F. MC / RFC / RFSU gates and certificates | Policy engine (`commissioning_readiness_policy.py`) and gates present | Implemented, insufficiently tested |
| G. Preservation | Blueprint `preservation.py` (392 lines), migration `20261117_0029` | Partially implemented; recurring-schedule timezone safety not verified |
| H. Document control and dossier | `DOCUMENT_TEMPLATES.md`, dossier export service (439 lines), revision migrations | Partially implemented |
| I. Excel import/export | `import_export.py` (608 lines) | Not verified against the 10-point import contract in the brief |
| J. Reporting and KPIs | Dashboard exists; percentage numerators and denominators not audited | Partially implemented |
| Field/mobile execution | Not evidenced | Not implemented |
| Offline architecture | Not implemented (correctly; no misleading indicator found) | Not implemented |

## 5. Test inventory

- 19 `test_*.py` modules under `tests/` (plus `conftest.py` and `run_tests.py`), **4,047 lines** and **129 `def test_` functions** (static count).
- CI coverage gates: 80% for core modules, 58% for commissioning modules.
- The commissioning coverage gate (58%) is below the core gate. This should be raised only after tests are added, not by lowering gates.
- Tests exist for: tenant isolation, commissioning access, workflows, number service, storage, evidence archive validation, account recovery (including PostgreSQL), readiness via workflows, legacy schema boundary, product boundary, UI localization.
Corrected after a second check (the first draft of this section was wrong):

- **Covered**: Excel dry-run import and export (`test_engineering_excel_exchange_dry_run_import_and_export`), formula-cell and scope rejection, Punch corrective-action and reopen rules, readiness policy configuration and per-gate Punch blockers, invalid policy fail-closed, preservation cycles and permissions and compliance report, serverless rejection of ephemeral evidence storage, storage path traversal, and SHA-256 checks in workflow tests.
- **Not found**: a dedicated Punch waiver test, PDF generation determinism, a storage round-trip against a real S3-compatible service, and preservation schedule timezone handling.

**Status: Partially implemented.** Test count is respectable but several brief-required categories have no identifiable test.

## 6. Production readiness gaps (not verified)

| Gap | Classification |
|---|---|
| S3 evidence backend has never been verified against a provider-compatible service (no credentials available in this session) | Blocked by external evidence |
| Backup and restore round-trip for evidence files (only PostgreSQL dump/restore is in CI) | Production verification required |
| Single authoritative deployment guide | Partially implemented (see §3.1) |
| Redis-backed rate limiting | CI sets `RATELIMIT_STORAGE_URI`; production wiring not verified |
| Deployed commit and URL verification | Blocked: no deployment access in this session |
| Latest CI run result on `main` | Not inspected (no API access from this session) |
| Trivy, Bandit and pip-audit results | Not executed in this audit |

## 7. Security observations

- `transition_witness` checks permissions server-side (`_need`, `has_permission`) before any state change, and enforces state transitions (`ATTENDED` only from `PLANNED` or `NOTIFIED`; `RELEASED` only from `ATTENDED`). Good.
- Witness evidence snapshots include SHA-256 checksums in the audit `before` payload.
- Not reviewed in depth in this phase: CSRF configuration, session cookie flags, TOTP implementation, rate limiting in code, upload size and MIME validation, XSS in templates. These belong to the Phase 1 security review.

## 8. Findings summary, priority and Phase 2 status

Phase 2 status (this branch):

| # | Finding | Status |
|---|---|---|
| 1 | Conflicting deployment documents | **Resolved in docs.** `DEPLOYMENT_GUIDE.md` is the single authoritative guide (Docker Compose). `DEPLOYMENT.md` is a pointer. Vercel is stated as not a production target. Stale head `20261116_0019` corrected to `20261117_0033` in `PRODUCTION_LAUNCH.md`, `ADMINISTRATOR_GUIDE.md` and `OPERA_ARCHITECTURE.md`. Not executed; document-only change. |
| 2 | Punch categories fixed to A/B/C/D | **Deferred, and narrowed.** Gate blocking is already configurable and tested. Making the category set itself configurable needs a model change, an Alembic migration, and updates to number generation, readiness policy, workflow, demo seed and tests. Not implemented: it cannot be validated without installed dependencies and a PostgreSQL run. |
| 3 | Test gaps | Open, narrowed to: waiver test, PDF determinism, real S3 round-trip, preservation timezone. No new tests written, because none can be executed here. |
| 4 | Commissioning coverage gate below core gate | Open. |
| 5 | No executed CI or lint evidence | Open. Dependencies could not be installed: the package index is unreachable from the audit environment. |
| 6 | Marketing draft with fabricated metrics | Not in `main`. Keep it out. |
| 7 | Advanced dependency types and critical path | Open. |

Original priority list:

| # | Finding | Priority |
|---|---|---|
| 1 | Three conflicting deployment documents; Vercel guide contradicts S3 implementation | High |
| 2 | Punch category set and labels fixed to A/B/C/D; gate blocking already configurable | High |
| 3 | Test gaps: waiver, PDF determinism, real S3 round-trip, preservation timezones | High |
| 4 | Commissioning coverage gate (58%) below core gate (80%) | Medium |
| 5 | No executed evidence of CI, linting or Docker build in this audit | High (verification) |
| 6 | Marketing draft in session contains fabricated metrics; not in `main` but must not be merged | Medium (prevention) |
| 7 | Advanced dependency types (SS, FF, SF) and critical path not evidenced | Medium |

## 9. What this audit does not claim

- It does not claim that OPERA is production-ready.
- It does not claim ICAPS parity or official endorsement.
- It does not claim any CI result, test pass or deployment.
- Every "Implemented" statement above is a code-reading judgement that must be confirmed by execution in Phase 7.

## 10. Next steps

1. Install dependencies in an environment with network access and run the CI commands locally (`ruff`, `mypy`, `pytest`, `bandit`, `pip-audit`).
2. Confirm the latest `main` CI run result.
3. Resolve the deployment document conflict and choose one production target.
4. Address findings 2 and 3 in Phase 2.
