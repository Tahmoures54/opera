# Project Readiness Policy

OPERA stores the commissioning readiness policy on each project. Only a project member with the `project.manage` permission can view or change it, through **Commissioning Operations → Readiness policy**.

The policy is OPERA configuration. It is not an imported ICAPS ruleset and does not replace the approved completion procedure, ITP, contract or authority matrix.

## Configurable controls

### Punch blockers by gate
Select which open Punch categories block each milestone independently:
- MC — Mechanical Completion
- RFC — Ready for Commissioning
- RFSU — Ready for Start-Up

The initial OPERA defaults are A and B for all three gates. A project may select any configured OPERA category (A/B/C/D) for each gate. Only Punch items in OPEN or IN_PROGRESS status are considered open blockers; CLOSED, VERIFIED and WAIVED records do not block through this rule.

### Required Check Sheet types by gate
Select the Check Sheet types whose existing records must be signed off for each milestone:
- PRE_COMM_A
- PRE_COMM_B
- COMM_C
- FUNCTIONAL_TEST
- HYDROTEST, LEAK_TEST, FLUSH_BLOW, MEGGER, CALIBRATION (mechanical test records; projects add them to the gates that need them)

The initial defaults require PRE_COMM_A and PRE_COMM_B for MC, and all four types for RFC and RFSU. By default, OPERA checks the registered sheets of the selected types. For **MC**, presence is also required by default: at least one registered sheet of every selected MC type must exist. For RFC and RFSU, presence is not required by default. Enable presence per gate, or the all-gates option, when the project procedure requires it.

### Task activities that block MC
Select the task activity types (CCK, STS, PIP, PRC, FTS, OTS, PVP) whose incomplete tasks block Mechanical Completion. A task is incomplete unless it is Completed or Cancelled. The default is empty, so MC is not gated on tasks until a project selects activity types. RFSU task completion is controlled separately below.

### Dossier documents for MC
MC also checks the project's active dossier document rules (Document requirements on the Operations page). A rule uses the latest revision of each document of the subsystem, matched on document type and discipline (or any discipline). It passes when enough matching documents are approved (if required) and have evidence (if required). Projects without dossier rules are not affected.

### Equipment statuses that block MC
Enter the equipment status values that prevent MC, for example PLANNED or NOT_INSTALLED. Status is free text on equipment, so use the exact values recorded in the equipment register. The default blocks only PLANNED and NOT_INSTALLED, so equipment with status ACTIVE is not affected.

### Hold points
Select the milestones blocked by unreleased Hold points linked to a Check Sheet. The initial default blocks MC, RFC and RFSU.

### RFSU task completion
The initial default requires every task in the subsystem to be Completed or Cancelled before RFSU. This requirement can be disabled only where the approved project procedure permits it; incomplete tasks remain visible as warnings.

## Evaluation and fail-safe behavior
- The policy is loaded from the same tenant-scoped project as the subsystem.
- Invalid or malformed persisted policy data causes MC, RFC and RFSU to fail closed until an authorized administrator saves a valid policy.
- The readiness result identifies the gate associated with every blocker.
- The handover service reports blockers for the specific milestone being attempted.
- MC and RFC certificates capture the effective policy, gate result, gate-specific issues and issue-time evidence in the immutable certificate snapshot.
- Policy changes are audited with before/after values. A later policy change does not rewrite previously issued certificate snapshots.

## Energy isolations (RFSU)
Energy isolations applied for work on a subsystem are recorded in the isolation register (commissioning managers and engineers manage it; all project members can view it). An isolation records the tag, energy type (electrical, pneumatic, hydraulic, mechanical, thermal, chemical, gravity or other), purpose and the person who applied it. **RFSU is blocked while any isolation is applied.** An isolation can be released only by a different person than the one who applied it, so removal is independently verified.

This implements a minimal subset of the energy isolation requirements in IOGP 577. It does not replace the site permit-to-work system, and it does not yet record multiple energy sources per equipment, shift-handover verification, or the isolation handover register for equipment transferred to operations.

## Punch waivers
Only the client representative can waive a Punch item (permission `punch.waive`). Managers and QC inspectors cannot waive. The waiver reason is recorded in the punch history and audit log.

## Requirements handled through dossier document rules
Vendor documentation, spare-parts lists, training records and utility-availability evidence are project-specific deliverables. Configure them as Document requirements on the Operations page rather than as separate modules. MC checks them when the rules are active for the project.

## Electronic signatures
Sign-off records use authenticated acknowledgement with an audit trail. This is not a qualified electronic signature. Part 11-style controls such as signature manifestation (printed name, date, time and meaning) and re-authentication at signing are not yet implemented. Choosing and implementing a qualified signature provider is a project decision, pending the applicable regulatory regime.

## Change control
Before saving a policy, the project administrator must obtain the required engineering/client approval. Record the governing procedure and revision in the project's controlled document register. Reassess the policy whenever the contract, ITP, systemization, Punch classification or commissioning authority matrix changes.

A saved policy is not proof that the selected rules are contractually correct. Project approval remains mandatory.
