# OPERA Punch List Lifecycle

OPERA's Punch List is an independently designed workflow. Project contracts and approved completion procedures remain authoritative for category definitions and acceptance criteria.

## Status transitions

| Current status | Allowed next status | Required evidence |
|---|---|---|
| OPEN | IN_PROGRESS | Assignment / work commencement |
| OPEN | WAIVED | Waiver reason and verification permission |
| IN_PROGRESS | CLOSED | Corrective action description |
| IN_PROGRESS | WAIVED | Waiver reason and verification permission |
| CLOSED | VERIFIED | Verification permission |
| CLOSED | IN_PROGRESS | Reopen reason; previous corrective action remains in history |

VERIFIED and WAIVED are terminal in the current workflow. A new defect should be raised as a new Punch item rather than silently changing a verified or waived record.

## Closure and reopening

- A Punch item cannot move to CLOSED without a corrective action statement.
- A CLOSED item cannot be reopened without a reason.
- Reopening clears the current closure fields and corrective action so the live register no longer implies the item is resolved.
- The previous corrective action, reopen reason, user, timestamp and before/after status remain in append-only PunchHistory and the audit log.
- A later closure records a new corrective action and closure timestamp.
- Category A/B Punch items continue to block MC/RF readiness until they are verified or formally waived under the project's permissions.

## Roles

- Raising and assigning permissions control work commencement and closure.
- Verification permission controls verification and waiver.
- Every transition is tenant-scoped, permission-checked and audited.

This workflow is not a substitute for project-specific Punch category definitions, client acceptance rules, safety controls or approved waiver authority.
