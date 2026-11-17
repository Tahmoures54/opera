# Witness, Hold and Review Point Lifecycle

OPERA records project inspection points against a Check Sheet or an individual Check Sheet item. The supported types are WITNESS, HOLD and REVIEW. These labels are configurable only through the project procedure and must not be interpreted as a substitute for the approved Inspection and Test Plan (ITP).

## Controlled states

| State | Meaning | Allowed next action |
|---|---|---|
| PLANNED | Point scheduled with a named notified party and date/time | NOTIFIED; WITNESS/REVIEW may be CANCELLED |
| NOTIFIED | Notification recorded with a server timestamp | ATTENDED; WITNESS/REVIEW may be CANCELLED |
| ATTENDED | Attendance and a recorded result captured | RELEASED |
| RELEASED | Authorized project manager records the release note | Terminal |
| CANCELLED | Point cancelled with a reason before attendance | Terminal |

An attended point cannot be cancelled or silently reopened. HOLD points cannot be cancelled through the ordinary lifecycle, even before attendance; a project-approved waiver/deviation process is required and must not be replaced by routine cancellation. If a witness/review inspection must be repeated, create a new point and preserve the original history.

## Authority

- Commissioning Manager: schedule, notify, release, or cancel a point before attendance.
- QC Inspector: record attendance and result; cannot release the point.
- Other roles: no transition permission unless a project-specific authorization is explicitly implemented.

## Required records

- Check Sheet and optional item association, point type, notified party and planned time.
- Server-recorded notification, attendance and release timestamps. The NOTIFIED transition records that a user has manually notified the named party; OPERA does not send email/SMS notifications.
- Attending user, release-authorizing user, attendance result, release note or cancellation reason.
- Append-only before/after audit snapshots for every state transition.

## Gate behavior and limitations

- A Check Sheet item configured as witness-required cannot be signed off until its associated witness points are released.
- HOLD points block configured MC/RFC/RFSU readiness gates while not released or cancelled.
- REVIEW points are tracked for review traceability; they do not automatically become a HOLD point.
- The application does not infer acceptance criteria, witness notice periods, waiver authority or statutory inspection rules. These must be defined by approved project procedures and the ITP.
- WitnessPoint does not yet have dedicated file-evidence attachments; the release note and audit trail are recorded, but supporting ITP evidence must remain in the controlled document/check-sheet record until that linkage is implemented.
- Authenticated user attribution is an application audit record, not a qualified electronic signature.

Production acceptance still requires project-specific role/authority approval, staging execution, database migration rehearsal and audit/evidence retention verification.
