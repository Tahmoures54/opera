# OPERA Workflow Guide

This guide describes the implemented baseline and distinguishes it from workflows still requiring configuration or development.

## 1. Project setup
1. A company-scoped administrator or project manager creates a project.
2. The project manager defines Systems and Subsystems.
3. Equipment / Tags are registered against a project and subsystem.
4. Project members are assigned OPERA roles. Roles do not alter the user's account-level role.

## 2. Commissioning Task Register
1. Open the project and choose **Task register**.
2. Assign a unique task number within the company.
3. Select the activity code, title, discipline, system and subsystem.
4. Optionally link equipment and a check sheet belonging to the same project/system/subsystem.
5. Record progress stage/substage, assigned group, estimated/spent man-hours and planned/actual dates.
6. The initial task state is **Not Started**. Authorized project managers can move tasks through the controlled execution lifecycle. Finish-to-start predecessor links block a successor from becoming Ready or In Progress until all predecessors are Completed. The dependency graph rejects self-links, duplicates, cross-project links and cycles.

Historical project ICAPS documentation describes activity codes CCK, STS, PIP, PRC, FTS, OTS and PVP. Their applicability and acceptance criteria must be confirmed against the current project procedure register.

## 3. Check Sheet execution
1. Create a Check Sheet under a project and subsystem.
2. Add inspection/test items and acceptance criteria.
3. Issue the sheet.
4. Record actual results as execution proceeds.
5. Required QC verification and two-party sign-off are enforced by the existing check-sheet workflow.
6. A signed-off sheet is immutable; create a controlled revision for corrections.

## 4. Punch management
1. Raise a Punch against the project/subsystem and optionally equipment or check sheet.
2. Assign the responsible person and target closure date.
3. Record corrective evidence.
4. Verify clearance independently where the role permits.
5. Waivers require a reason and an authorized role.

The existing A/B/C/D values are OPERA's current configuration. They must be aligned with the project's contract and client procedure before production use.

## 5. Witness / Hold / Review
Witness points can be scheduled against check-sheet items, attended and released through the existing workflow. Hold points linked through Check Sheets are included in readiness evaluation. Project-specific witness/hold categories, release authorities, blocking matrix and automatic escalation policy still require approval/configuration.

## 6. MC / RFC / RFSU handover
The user-facing milestone terminology is:

1. **MC — Mechanical Completion:** mechanical completion and applicable pre-commissioning prerequisites.
2. **RFC — Ready for Commissioning:** release to begin commissioning.
3. **RFSU — Ready for Start-Up:** commissioning/start-up prerequisites accepted before start-up authorization.
4. **Operations Acceptance:** formal Operations acceptance or rejection.

**Current implementation:** OPERA issues immutable `MC` and `RFC` certificate records. The handover sequence is DRAFT → MC_CERTIFIED → RFC_CERTIFIED → RFSU → ACCEPTED. RFC is Ready for Commissioning; RFSU is a distinct readiness/authorization gate and is not another name for RFC. The former RF naming is retained only where required for backward-compatible routes or legacy data. MC/RFC issuance captures an issue-time evidence snapshot and audit event. The project manager configures the gate-specific Punch categories, required Check Sheet types, Hold-point gates and RFSU task completion under **Commissioning Operations → Readiness policy**. See [READINESS_POLICY.md](READINESS_POLICY.md). The exact policy and signatory matrix must be approved for each project; OPERA defaults are not universal contractual rules.

## 7. Progress reporting
Progress snapshots can be recorded at project, system or subsystem scope. They include Check Sheet counts/weights, task counts/estimated-man-hour weights and Punch counts. Cancelled tasks are excluded; when all eligible task hours are zero, task count weighting is used. Empty registers do not imply 100% completion. System/Subsystem weight_percent values are not yet rolled up into a contractual project-wide percentage; obtain approval of the project progress measurement procedure before contractual reporting.

## 8. Production evidence
Use only actual project records. Do not use sample/demo records as evidence of completion. Every rejected, reopened, waived or approved action must retain its reason and audit history.


## Commissioning task execution lifecycle

The Task Register supports controlled execution-state changes for project managers and commissioning managers:

- `NOT_STARTED → READY`
- `READY → IN_PROGRESS`
- `READY → BLOCKED`
- `IN_PROGRESS → BLOCKED`
- `IN_PROGRESS → COMPLETED`
- `BLOCKED → IN_PROGRESS`
- `NOT_STARTED / READY / IN_PROGRESS / BLOCKED → CANCELLED` (where explicitly permitted by the transition matrix)
- `COMPLETED → IN_PROGRESS` for a controlled reopen.

The application rejects transitions outside the matrix. A reason is mandatory when blocking or cancelling a task and when reopening a completed task. First entry into `IN_PROGRESS` records the actual start date; completion records the actual finish date. Reopening clears the prior actual finish date but preserves the first actual start date. Every accepted transition writes a tenant-scoped audit event with before/after state and reason in the same database transaction.

This is an OPERA workflow design informed by commissioning execution needs; it is not a claim that every ICAPS release uses these exact status labels or transition rules. Project-specific procedures and the licensed ICAPS version remain authoritative.


## 9. Engineering Document Register and revision control

The project **Document Register** stores engineering documents by document number and controlled revision. Each revision is a separate record and can be linked to a project System, Subsystem and Equipment tag.

1. Register a document number, title, document type, discipline and optional system hierarchy links. The initial revision is A.
2. Upload the controlled document file. OPERA stores its checksum and evidence metadata through the commissioning evidence service.
3. Submit the revision for review. A file is required before submission.
4. An authorized reviewer may reject the revision with mandatory comments. An authorized approver may approve it.
5. The document author cannot approve or reject their own revision.
6. A new revision can be created from an approved or rejected revision. The previous approved revision becomes superseded; the prior record and its review evidence remain available.
7. Review decisions and state changes are recorded in the append-only commissioning audit history.

The current role mapping grants document creation to commissioning managers and engineers, review to QC inspectors and client representatives, and approval to commissioning managers and client representatives. These are OPERA defaults and must be confirmed against the project's Document Control Procedure, authority matrix and client requirements.

The current implementation is a controlled register and review baseline. It does not yet provide a full transmittal workflow, external document numbering integration, bulk register import/export, configurable review cycles, electronic signature compliance, or a durable object-storage adapter for serverless Production. Do not treat a stored approval as a legally binding electronic signature unless the project's approved signature process has been configured and validated.


## 10. Subsystem Completion Dossier

Open **Subsystem Completion Dossier** from the commissioning operations dashboard. The dossier consolidates the latest registered revision for each document number, Check Sheets, Punch items, Witness/Hold points, equipment tags and commissioning tasks for one subsystem.

The readiness panel currently evaluates four configured indicators:
- At least one Check Sheet exists and every registered Check Sheet is signed off.
- At least one current engineering document exists and every current revision is approved.
- No open Category A or B Punch items remain.
- No Hold point remains pending release.

Category C/D Punch items and incomplete commissioning tasks remain visible for review but are not currently hard blockers in this dossier score. A missing document register or empty Check Sheet register is shown as not ready, not treated as completed.

The dossier is a readiness overview only. It is not a generated MC certificate, and this initial increment does not automatically change a Handover Package status. The project must approve its dossier index, required document types, Punch category rules, witness/hold rules and task completion criteria before these indicators can be treated as contractual acceptance gates.


## 11. Task dependencies and execution sequence

Project managers can add finish-to-start (FS) predecessor links between tasks in the same project and subsystem. Optional lag is recorded as a non-negative number of calendar days. A successor cannot be moved to **Ready** or **In Progress** until every predecessor is **Completed**.

The dependency graph rejects self-links, duplicate links and circular sequences. Removing a link is permission-controlled and audited. This release intentionally implements FS only; SS, FF and SF relationships, negative leads, automatic date rescheduling and critical-path calculations are not implied. A lag is recorded for planning visibility and is not yet used to automatically move planned dates.

Dependencies are an execution control, not a substitute for approved project logic. The project scheduler remains responsible for validating the sequence and planned dates.


## 12. Weighted progress measurement

The operations dashboard can save progress snapshots at project, system or subsystem scope. Each snapshot records the reporting date, signed Check Sheet count and weight, Punch closure counts, and commissioning task completion.

- Check Sheet count progress is signed-off sheets divided by all sheets in the selected scope.
- Weighted Check Sheet progress is the sum of signed-off sheet weights divided by all sheet weights.
- Task count progress is completed tasks divided by non-cancelled tasks.
- Task weighted progress uses estimated man-hours as weights. If all eligible tasks have zero estimated hours, the calculation falls back to task count progress.
- Cancelled tasks are excluded from task progress. A missing register is reported as 0%, not 100%.

Project, System and Subsystem snapshots are stored independently and audited. The current implementation does not combine the System/Subsystem weight_percent fields into a project-wide roll-up; project weight allocation and progress measurement bases must be approved in the project's progress measurement procedure before contractual reporting.


## 13. Configurable subsystem dossier index
Project managers can define mandatory current engineering document types for each subsystem dossier from **Commissioning Operations → Configurable dossier index**. Each rule specifies document type, discipline (or ANY), minimum count, approval requirement and whether an attachment record is required. OPERA evaluates only the latest revision of each document number and shows a per-rule PASS/MISSING result. If no active rules exist, the default remains at least one current engineering document with all current revisions approved. See [DOSSIER_INDEX.md](DOSSIER_INDEX.md).

This is a dossier completeness/readiness view, not a generated PDF/ZIP turnover package and not a certificate issuance action.


## 14. Equipment preservation
Open **Commissioning Operations → Preservation** to register equipment-specific plans from approved procedures/OEM instructions. Record the procedure reference/revision, positive interval and initial next-due date. Inspectors record findings and outcomes; non-compliant results require corrective action and place the plan in ACTION_REQUIRED until a compliant follow-up is recorded. Inspection history is append-only and can carry evidence attachments. See [PRESERVATION_GUIDE.md](PRESERVATION_GUIDE.md).


## 15. Check Sheet and Test Sheet templates
Managers create a DRAFT template from Commissioning Operations, define its type, discipline, optional equipment type, overall acceptance criteria and inspection items, then approve it. Approved templates are immutable. Create a new revision to change approved content; approval of the new revision retires the previous one. When a Check Sheet is created from an approved template, OPERA snapshots the template revision and creates the item register. See [CHECKSHEET_TEMPLATES.md](CHECKSHEET_TEMPLATES.md).
