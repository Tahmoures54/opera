# OPERA Functional Gap Analysis

**Baseline:** PR #43 head commit 3a200612f40844b91f63d8dfa136f9b8a99b2e1e, based on main commit d2734582146c5faed42043f426eeb94fede7dfea, 17 November 2026.  
**Evidence basis:** current models/routes/services and merged PRs #21–#29, #31, #39, #40 and #42. PR #39 CI run 44084364501, PR #40 CI run 44086055925 and PR #42 CI run 44087919325 passed quality, integration and docker jobs on their respective PR heads. PR #43 CI run 44090572416 passed quality, PostgreSQL integration and Docker checks. This is a code-level capability assessment, not production acceptance.

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
| Check Sheet execution | Implemented bounded scope | Issue, item results, independent QC verification, two-party sign-off, rejection/rework, controlled revisions; project-scoped DRAFT/APPROVED/RETIRED templates with immutable approved revisions, execution snapshots, equipment/discipline matching, mandatory/optional items, acceptance criteria, units and witness-release gates | Advanced measurement capture, configurable result vocabularies, qualified e-signatures, cross-project template sharing and generated blank form packs |
| Punch List | Implemented bounded scope | Raise/assign, corrective action, closure, audited reopen, history, verification and waiver evidence; milestone blocking categories are project-configurable | Project-configurable category definitions/meanings, waiver authority matrix and further clearance workflow controls |
| Witness / Hold / Review | Partial | Scheduling, attendance/release; Hold-point blocking can be configured per MC/RFC/RFSU gate | Witness/review point requirements, overdue escalation and full authority matrix remain incomplete |
| MC / RFC / RFSU | Implemented bounded scope | Immutable MC/RFC certificates; project-configurable Punch, Check Sheet, Hold-point and RFSU task rules; invalid policy fails closed; policy and gate issues captured in certificate snapshots | Project-specific signatory matrix, qualified electronic signatures and further procedure-linked approvals |
| Operations Acceptance | Implemented baseline | Authorized accept/reject transition after RFSU with audit | Full custody-transfer package and project-specific acceptance checklist |
| Document Register | Implemented bounded scope | Revision records, evidence upload metadata, review/approval/rejection and history | Transmittals, bulk exchange, external numbering and configurable review cycles |
| Engineering Excel exchange | Implemented bounded scope | OPERA XLSX template/export, dry run, row validation, SHA-256 confirmation, create-only atomic import and audit | More registers, revision-delta workflows, controlled retire/modify actions |
| Subsystem dossier | Implemented bounded scope | Evidence-based readiness view and configurable document index; immutable numbered snapshots; DRAFT/IN_REVIEW/APPROVED/REJECTED/ISSUED workflow; separate author/reviewer/issuer controls; append-only review history; SHA-256 integrity checks; controlled issued PDF/ZIP exports; legacy working exports remain explicitly uncontrolled | Configurable dossier sections and authority matrix, Operations Acceptance linkage, qualified signatures and production evidence-retention/restore validation |
| Progress reporting | Partial | Scoped snapshots, Check Sheet/Task count and weight metrics, Punch counts | Approved project/system roll-up, daily/weekly reports and contractual progress procedure |
| Preservation | Partial | Project-scoped equipment plans, approved procedure/revision references, user-supplied interval/due date, append-only inspection history, compliant/non-compliant/not-applicable outcomes, corrective action, environmental conditions and evidence attachments | Plan revision editing, recurring calendar/reminders, preservation check-sheet templates, trend/compliance reports and durable production evidence storage |
| Manpower / resource planning | Partial | Task estimated and spent man-hour fields | Timesheets/work logs, capacity, contractor allocation and approvals |
| Evidence storage | Implemented backend; production acceptance pending | Tenant-scoped local and S3-compatible backends, extension/content checks, size limit, SHA-256 metadata, server-side AES-256 request, serverless rejection of ephemeral local uploads, automated storage tests | Configure a real private bucket, migrate and checksum-verify existing evidence, verify provider-side retention/versioning, malware scanning and paired database/object backup-restore; live provider round-trip remains outstanding |
| Reporting catalogue | Evidence-limited | OPERA dashboards and stored progress snapshots | Exact ICAPS catalogue/formulas unavailable; do not claim the advertised 30+ report catalogue |
| Current ICAPS parity | Evidence-limited | Public product capability baseline and historical references documented in ICAPS_ANALYSIS.md | Current release manual, administrator guide, import annex and authorized representative sample files |

## Critical operational risks before production
1. **Evidence durability:** the S3-compatible storage adapter is merged, and serverless uploads fail closed when local storage is selected. Production evidence use still requires bucket configuration, migration/checksum verification of any existing files, provider access/retention controls and a successful backup/restore rehearsal.
2. **Readiness policy:** current A/B Punch and Check Sheet defaults must be reviewed and approved against the project's completion procedure, ITPs, contract and authority matrix.
3. **Electronic signatures:** authenticated acknowledgement is not a qualified cryptographic signature.
4. **Dossier:** controlled revision, review, approval and issue workflow is implemented in the pending branch. It is an OPERA record-control mechanism, not a qualified electronic signature or automatic contractual acceptance. Project-specific section/authority rules and staging acceptance remain required.
5. **Preservation:** automated reminders, recurring schedules, plan revisions and advanced compliance reports are not implemented; evidence retention depends on completing production S3 configuration and backup controls.
6. **Production acceptance:** successful CI does not establish production migration, deployment, backup/restore or multi-party project acceptance.

## Recommended implementation order
1. Validate the controlled dossier lifecycle in staging; extend project-configurable dossier sections and authority matrices.
2. Durable evidence storage and security/retention/restore controls.
3. Advanced Check Sheet measurement capture, configurable result vocabularies and generated blank/test form packs.
4. Preservation reminders, plan revisions, templates and compliance reporting.
5. Work logs/manpower and expanded reports.
6. Further document-control and engineering import/revision workflows.
7. Procedure-linked witness, signatory and waiver authority configuration.

## Acceptance evidence
A capability is complete only when its model constraints, migrations, backend service, route authorization, UI, audit history, tenant-isolation tests, rejection-path tests and relevant output tests are verified. Production readiness additionally requires a staging acceptance scenario, production-equivalent database migration test and evidence backup/restore rehearsal.

## Reverse-engineering boundary
The public ICAPS product pages and historical manuals establish a conceptual reference only. They do not establish current workbook schemas, revision semantics, current role matrix, punch category rules, exact report formulas or current form layouts. OPERA's workbook, state machines and forms are independently designed; no proprietary ICAPS behavior is inferred where evidence is absent.
