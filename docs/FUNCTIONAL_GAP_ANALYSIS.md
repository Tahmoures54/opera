# OPERA Functional Gap Analysis

**Baseline:** repository `main` as of 17 November 2026 (post Readiness Engine commit).  
**Evidence rule:** “Present” means code/model/route evidence was observed; “partial” means some foundation exists but the lifecycle or coverage is incomplete. Historical ICAPS references are not treated as current product specifications.

## Status legend
- **Present and complete:** verified end-to-end for the stated bounded scope.
- **Present but incomplete:** a working foundation exists, but meaningful lifecycle or coverage remains.
- **Requires development:** no sufficient implementation was found.
- **Requires redesign:** existing structure needs material change.
- **Not transferable:** proprietary/product-specific behavior or unsupported assumption.
- **Needs more documentation:** exact ICAPS behavior cannot yet be verified.

## Capability matrix

| ICAPS / OPERCOM capability | Functional intent | OPERA baseline | Gap | Priority | Implementation |
|---|---|---|---|---|---|
| Project setup | Project/client/contractor and dates | Present | Project-specific configuration and phases need extension | P1 | Extend existing project model; avoid duplicate project core |
| Organization / roles | Separate administrator, superintendent, executor responsibilities | Partial | OPERA project roles exist; configurable groups and discipline ownership are limited | P1 | Role/permission matrix and group register |
| System / subsystem | Physical breakdown for completion scope | Present but incomplete | Limits, WBS and optional subproject levels need definition | P1 | Extend current hierarchy only where approved |
| Equipment / Tag | Equipment register tied to subsystem | Present but incomplete | Engineering attributes, import mapping and tag status lifecycle need extension | P1 | Equipment data dictionary and import validation |
| Task branch | Task register connected to equipment and progress sequence | Present | Task dependencies exist; controlled status transitions and full execution records remain | P1 | Task model + dependency + status service |
| Task activity taxonomy | CCK/STS/PIP/PRC/FTS/OTS/PVP | Present | Confirm codes against project manual and map to client procedure library | P1 | Controlled enum; configurable catalog later |
| Discipline association | One or more disciplines per task | Partial | Current task record stores one discipline string | P1 | Add normalized task-discipline association after requirements confirmed |
| Progress stage/substage | Sequence and progress classification | Partial | Free-text stage/substage does not yet enforce a project sequence | P1 | Configurable sequence register and predecessor rules |
| Check/test sheets | Execute and record checks with acceptance criteria | Present but incomplete | Sheet library, reusable templates, richer witness/result controls and controlled revisions | P1 | Template definitions and project-specific sheet instances |
| Check-sheet revision | Preserve signed records and issue revisions | Partial | Existing revision/immutability foundation; full transmittal/review workflow needs validation | P1 | Revision register and tests |
| Punch list | Raise, assign, clear, verify and close defects | Present but incomplete | Reopen and configurable category/closure matrix need completion | P1 | Explicit state machine and category policy |
| Witness / Hold / Review | Notify, attend, record and release points | Present but incomplete | Hold-point blocking behavior and overdue/escalation logic need verification | P1 | Workflow guardrails and evidence |
| MC / RF / RFSU handover | Certificates and milestone-based transfer | **Present** (Readiness Engine) | Certificate PDF artefacts and full dossier packaging still incomplete | P1 | `services/commissioning_readiness.py` evaluates gates; PDF/dossier next |
| Document register | Controlled document metadata, revisions and status | Requires development | No complete standalone register found | P1 | Document register, revision and transmittal workflow |
| Import / Export | Excel-based engineering data exchange | Present | Versioned templates + dry-run already implemented | P1 | OPERA-owned XLSX templates and import pipeline |
| Dossier compilation | Compile approved evidence by subsystem/discipline | Partial | Handover package exists; indexed dossier generation is incomplete | P1 | Dossier index, completeness checks and PDF export |
| Preservation | Periodic preservation plans and check sheets | Requires development | Dedicated module not observed | P2 | Add only when project scope requires it |
| Reporting | Actual execution progress and outstanding items | **Present** (weighted progress) | Task + CheckSheet weighted progress helper added; richer dashboards remain | P1 | `calculate_subsystem_progress` in readiness service |
| PDF / print | Controlled, printable forms and certificates | Partial | Output catalog and revision-aware rendering need completion | P1 | Server-generated, versioned PDF outputs |
| Daily / weekly progress | Period reporting | Requires development | No verified operational report workflow | P2 | Derive from dated task/checksheet/punch events |
| Resource / man-hours | Estimate and actual hours | Partial | Task register captures estimate/spent fields; timesheet evidence and approval absent | P2 | Add daily work logs if contract requires |
| Audit trail | Record who changed what and when | Present but incomplete | Generic audit exists; coverage must include all new transitions | P1 | Append-only events and tests |
| Attachments | Evidence linked to entity | Present but incomplete | Local/serverless filesystem is ephemeral on Vercel | P1 | Durable object storage adapter before production evidence use |
| Advanced reports catalogue | ICAPS advertises 30+ reports | Needs more documentation | Exact catalogue and formulas not available | P2 | Map only after authorized catalogue is supplied |
| Current ICAPS forms and field rules | Exact product release parity | Needs more documentation | No current manual / workbook samples supplied | P1 | Evidence intake and field-by-field mapping |

## Priority order (updated)

1. P1 — task register and controlled sequence → **largely complete**.
2. P1 — readiness / certificate gates → **implemented** (`commissioning_readiness.py`).
3. P1 — weighted progress formulas → **implemented**.
4. P1 — document register and controlled revisions.
5. P1 — durable evidence storage for Vercel.
6. P1 — explicit workflow state machines and authorization tests (ongoing).
7. P1 — dossier packaging and certificate PDF artefacts.
8. P2 — preservation, resource planning and expanded reporting once contract scope is known.

## Acceptance evidence required before calling a capability complete

- Model constraints and migration tested on SQLite and PostgreSQL.
- Route tests include tenant isolation and role denial.
- Workflow tests verify allowed and rejected transitions.
- Output tests verify document content and revision metadata.
- CI green on the merge commit.
- Production deployment points to the same commit and health checks pass.

## Notes on reverse-engineering boundary

The Readiness Engine implements the *intent* of OPERCOM handover gates (no open A/B punches, signed pre-commissioning sheets, released holds, etc.) using only OPERA’s own models. It does not reproduce any proprietary ICAPS form, certificate layout, or internal calculation formula.
