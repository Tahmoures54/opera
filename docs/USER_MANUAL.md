# OPERA User Manual

## Sign in
Use the organization account provided by your administrator. OPERA uses the existing account and company identity. Project access is separately granted by project membership.

## Open a project
From the OPERA dashboard, open an existing project or create one if your account has project-management permission.

## Maintain project structure
Create Systems and Subsystems using the project structure screen. Register equipment against the correct subsystem. Check project codes, system codes, subsystem codes and Tag numbers before creating execution records.

## Maintain the Task Register
Open **Task register** from the project structure page. Create tasks using the project-controlled task number and correct activity code. Select the matching System and Subsystem. An equipment or Check Sheet association is optional but, if provided, must belong to the selected hierarchy. Enter realistic man-hours and dates; never use estimated values as actual progress.

## Execute Check Sheets
Open project operations, create a Check Sheet and add inspection/test items with acceptance criteria. Issue the sheet before execution. Record actual results and remarks. Follow witness and QC verification requirements. Only authorized users may sign or reject a sheet.

## Raise and clear Punch items
Record a concise defect description, correct subsystem/equipment, category, responsible person and target date. Add evidence and corrective action. A closure request is not the same as independent verification. Do not waive a Punch without an authorized decision and reason.

## Readiness milestones and handover
Use handover packages to collect subsystem milestone and acceptance information. The standard OPERA terminology shown in user-facing guidance is:

1. **MC — Mechanical Completion:** completion of mechanical/construction scope and applicable pre-commissioning prerequisites.
2. **RFC — Ready for Commissioning:** release of the subsystem to enter commissioning under the approved project procedure.
3. **RFSU — Ready for Start-Up:** commissioning and start-up prerequisites have been accepted before the start-up authorization process.
4. **Operations Acceptance:** formal acceptance or rejection of the handover package by the authorized Operations representative.

**Current implementation:** OPERA issues separate immutable `MC` and `RFC` certificate records. RFSU is a distinct readiness/authorization gate after RFC, not an RFC certificate. The legacy RF route/data alias is retained only for backward compatibility. The certificate stores the authenticated issuer, issue date, issue-time evidence snapshot and audit event. Project-approved completion procedures and signatory authority remain authoritative.

## Data integrity
Do not share accounts. Do not overwrite signed records. Report incorrect project mappings immediately. Do not upload personal or unrelated sensitive data as evidence.


## Equipment Preservation
The Preservation page lists equipment-specific preservation plans, their approved procedure references, due dates and inspection history. Only project-approved procedures/OEM instructions may determine preservation activities and intervals. A non-compliant inspection requires corrective action and keeps the plan in ACTION_REQUIRED until a compliant follow-up inspection is recorded. See [PRESERVATION_GUIDE.md](PRESERVATION_GUIDE.md).


## Check Sheet templates
A Check Sheet may be created manually or from an approved project template. Template-based sheets retain a snapshot of the template revision and item definitions used at creation. Mandatory items, failed results, independent QC verification and witness release are enforced before sign-off. See [CHECKSHEET_TEMPLATES.md](CHECKSHEET_TEMPLATES.md).
