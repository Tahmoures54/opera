# Equipment Preservation Management

OPERA's Preservation module records equipment-specific preservation plans and append-only inspection history. It is designed to track instructions from approved project procedures and OEM manuals; it does not supply or invent preservation limits.

## Plan setup
A user with `preservation.manage` creates a plan with:
- Unique project plan number
- Equipment/tag
- Preservation activity
- Procedure reference and revision
- Approved interval in days
- Initial next-due date
- Responsible company and optional assigned user
- Notes

The procedure reference, revision, interval and due date must be taken from the approved project procedure or OEM instruction. OPERA validates that the interval is a positive integer; it does not impose a technical preservation frequency.

## Inspection workflow
A user with `preservation.execute` records:
- Inspection date
- COMPLIANT, NON_COMPLIANT or NOT_APPLICABLE result
- Findings
- Environmental conditions where applicable
- Corrective action (mandatory for NON_COMPLIANT)
- Supporting evidence attachments

Every inspection snapshots the procedure reference/revision and interval used at the time. Inspection records are append-only. Corrections require a new inspection record, not mutation of the previous result.

### Schedule behavior
- **COMPLIANT:** last-performed date is updated, next due date becomes performed date + the plan interval, and the plan returns to ACTIVE.
- **NON_COMPLIANT:** corrective action is mandatory; the plan becomes ACTION_REQUIRED and its due date is set to the inspection date until a compliant follow-up is recorded.
- **NOT_APPLICABLE:** the inspection is logged without changing the plan schedule or status.

A plan may be suspended or closed by a preservation manager. Closed plans cannot be reactivated. An ACTION_REQUIRED plan cannot be manually reactivated; it requires a compliant follow-up inspection.

## Due indicators
The dashboard reports:
- OVERDUE when an active plan's next due date is before today
- DUE SOON when its next due date is within the next seven calendar days
- ON SCHEDULE otherwise
- ACTION REQUIRED, SUSPENDED or CLOSED according to plan state

The seven-day dashboard window is an OPERA display indicator, not an engineering acceptance criterion.

## Evidence and audit
Inspection events, plan changes and evidence uploads are audited. Attachments are stored using OPERA's current evidence-storage adapter. The current local-filesystem adapter is not durable on Vercel/serverless; configure private object storage and backup/restore before relying on uploaded preservation evidence in production.

## Known limitations
- No automated reminder/notification delivery is configured yet.
- No recurring calendar/shift planner or OEM interval library is included.
- The module does not create a preservation check-sheet template catalogue.
- Full preservation compliance reports and project-wide trend charts remain future work.
- Plan edits are not yet supported as revisions; close and create a new plan when the approved procedure changes, preserving the old plan/inspection history.
