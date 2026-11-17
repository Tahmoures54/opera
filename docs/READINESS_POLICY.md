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

The initial defaults require PRE_COMM_A and PRE_COMM_B for MC, and all four types for RFC and RFSU. By default, OPERA checks the registered sheets of the selected types; it does not require a sheet of every selected type to exist. Enable **Require at least one registered Check Sheet for every selected type** when the project procedure requires presence as well as sign-off.

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

## Change control
Before saving a policy, the project administrator must obtain the required engineering/client approval. Record the governing procedure and revision in the project's controlled document register. Reassess the policy whenever the contract, ITP, systemization, Punch classification or commissioning authority matrix changes.

A saved policy is not proof that the selected rules are contractually correct. Project approval remains mandatory.
