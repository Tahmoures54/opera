# OPERA Functional Gap Analysis

**Baseline:** `main` at commit `ca37db49224160628e9fb28d3b7d51930acc099f`, 17 November 2026.  
**Evidence basis:** merged PRs #21–#29 and #31, current models/routes/services, and successful `quality`, `integration` and `docker` checks on the baseline commit. This is a code-level capability assessment, not production acceptance.

## Status definitions
- **Implemented baseline:** code, route/UI and automated workflow coverage exist for the stated bounded scope.
- **Partial:** a working foundation exists but important lifecycle or operational requirements remain.
- **Not implemented:** no sufficient end-to-end implementation is present on main.
- **Evidence-limited:** exact current ICAPS behavior cannot be verified from available public sources.

## Capability matrix

| Capability | Main-branch status | Verified implementation | Remaining gap |
|---|---|---|---|
| Project / System / Subsystem | Partial | Tenant-scoped project and system/subsystem structure | Optional subproject/area/basic-function hierarchy and project systemization policy |
| Equipment / Tag Register | Partial | Equipment register and task/checksheet/punch/dossier relationships | Broader engineering attributes, discipline catalog and lifecycle/status governance |
| OPERCOM activity taxonomy | Implemented baseline | CCK, STS, PIP, PRC, FTS, OTS, PVP | Project-approved catalog, templates and applicability rules |
| Task Register | Implemented baseline | Task creation, controlled state transitions, actual dates, audit events | Task-to-multiple-disciplines/document links and configurable workflow templates |
| Task sequencing | Implemented bounded scope | Finish-to-start dependencies, lag storage, duplicate/self/cycle and project-scope validation; predecessor completion gate | SS/FF/SF, leads, automatic rescheduling and critical-path calculation |
| Check Sheet execution | Implemented bounded scope | Issue, item results, independent QC verification, two-party sign-off, rejection/rework, controlled revisions and immutability | Reusable template catalogue, richer measurements, controlled witness matrix and qualified e-signatures |
| Punch List | Implemented bounded scope | Raise/assign, corrective action, closure, audited reopen, history, verification and waiver evidence | Project-configurable category definitions and milestone blocking/waiver matrix |
| Witness / Hold / Review | Partial | Scheduling, attendance/release and Hold-point readiness blocking | Project-configurable witness rules, overdue escalation and complete authority matrix |
| MC / RFC / RFSU | Implemented bounded scope | Immutable MC and RFC certificates with issue-time evidence; distinct RFSU gate | Configurable readiness rules and certificate signatory matrix; qualified electronic signatures |
| Operations Acceptance | Implemented baseline | Authorized accept/reject transition after RFSU with audit | Full custody-transfer package and project-specific acceptance checklist |
| Document Register | Implemented bounded scope | Revision records, evidence upload metadata, review/approval/rejection and history | Transmittals, bulk exchange, external numbering and configurable review cycles |
| Engineering Excel exchange | Implemented bounded scope | OPERA XLSX template/export, dry run, row validation, SHA-256 confirmation, create-only atomic import and audit | More registers, revision-delta workflows, controlled retire/modify actions |
| Subsystem dossier | Partial | Evidence-based readiness view across current documents, Check Sheets, Punch, Hold points, tags and tasks; project-configurable document index with type/discipline/minimum-count/approval/evidence rules | Generated revision-controlled PDF, ZIP evidence package, dossier revision/approval workflow and durable evidence-byte verification |
| Progress reporting | Partial | Scoped snapshots, Check Sheet/Task count and weight metrics, Punch counts | Approved project/system roll-up, daily/weekly reports and contractual progress procedure |
| Preservation | Not implemented | — | Preservation plans, intervals, inspections, evidence, corrective actions and overdue reports |
| Manpower / resource planning | Partial | Task estimated and spent man-hour fields | Timesheets/work logs, capacity, contractor allocation and approvals |
| Evidence storage | Partial / production blocker | Private tenant/entity-scoped local storage, extension/content checks, size limit and SHA-256 metadata | Durable private object storage for serverless production, malware scanning, retention and restore rehearsal |
| Reporting catalogue | Evidence-limited | OPERA dashboards and stored progress snapshots | Exact ICAPS catalogue/formulas unavailable; do not claim the advertised 30+ report catalogue |
| Current ICAPS parity | Evidence-limited | Public product capability baseline and historical references documented in ICAPS_ANALYSIS.md | Current release manual, administrator guide, import annex and authorized representative sample files |

## Critical operational risks before production
1. **Evidence durability:** local filesystem storage is not suitable for Vercel/serverless persistence. Configure and test durable private object storage before using OPERA as the system of record for project evidence.
2. **Readiness policy:** current A/B Punch and Check Sheet defaults must be reviewed and approved against the project's completion procedure, ITPs, contract and authority matrix.
3. **Electronic signatures:** authenticated acknowledgement is not a qualified cryptographic signature.
4. **Dossier:** the subsystem page is a readiness view, not yet a complete indexed turnover package.
5. **Production acceptance:** successful CI does not establish production migration, deployment, backup/restore or multi-party project acceptance.

## Recommended implementation order
1. Project-configurable readiness and Punch/Check Sheet policy.
2. Reusable revision-controlled Check Sheet/Test Sheet templates.
3. Dossier index, completeness engine, PDF/ZIP compilation.
4. Durable evidence storage and security/retention/restore controls.
5. Preservation management.
6. Work logs/manpower and expanded reports.
7. Additional engineering import registers and controlled revision delta workflows.

## Acceptance evidence
A capability is complete only when its model constraints, migrations, backend service, route authorization, UI, audit history, tenant-isolation tests, rejection-path tests and relevant output tests are verified. Production readiness additionally requires a staging acceptance scenario, production-equivalent database migration test and evidence backup/restore rehearsal.

## Reverse-engineering boundary
The public ICAPS product pages and historical manuals establish a conceptual reference only. They do not establish current workbook schemas, revision semantics, current role matrix, punch category rules, exact report formulas or current form layouts. OPERA's workbook, state machines and forms are independently designed; no proprietary ICAPS behavior is inferred where evidence is absent.
