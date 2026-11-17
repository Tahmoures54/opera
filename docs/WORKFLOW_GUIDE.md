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
6. The initial task state is **Not Started**. Task sequencing, predecessor logic and controlled status transitions are not yet implemented in this increment.

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
Witness points can be scheduled against check-sheet items, attended and released through the existing workflow. The complete project-specific hold-point blocking matrix and automatic escalation policy remain to be implemented/confirmed.

## 6. MC / RF / RFSU handover
The current handover package stores milestone references and acceptance information. Full certificate generation, dossier completeness rules and every contractual gate are not yet equivalent to a controlled client-approved completion procedure.

## 7. Progress reporting
Existing snapshots are based on stored check-sheet and Punch data. The new Task Register is not yet included in the official progress formula. Until the weighting method is approved and implemented, do not use task counts or task man-hours as a substitute for contractual progress.

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
