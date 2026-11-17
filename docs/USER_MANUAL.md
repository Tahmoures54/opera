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


## Subsystem dossier exports

Open the subsystem's Completion Dossier page to review its current engineering documents, Check Sheets, Punch List, commissioning tasks, Preservation records and readiness checks.

- Export PDF produces a printable point-in-time register and readiness summary.
- Export ZIP + Evidence includes the PDF, a JSON manifest and the evidence files currently linked to the dossier records. Each included file is verified against its stored SHA-256 checksum.
- The ZIP export is rejected if a registered evidence file is missing or its checksum does not match.

Important: these downloads are labelled UNCONTROLLED_WORKING_EXPORT. They are not issued MC/RFC certificates, approved turnover dossiers or proof of contractual acceptance. Dossier revision numbering, review/approval and controlled issue remain separate work.


## Reusable Check Sheet and Test Sheet templates

Project managers can create a draft template in Commissioning Operations. A template contains a unique code, title, sheet type, discipline, optional equipment type, overall acceptance criteria and 1–100 inspection items. Each item can define expected result, acceptance criteria, unit, mandatory/optional status and witness requirement.

After approval, a template is immutable. Use Create next revision to prepare changes; the new revision remains a draft until approved. When the new revision is approved, the previous approved revision is retired. Existing Check Sheets retain the exact template revision and item snapshot from which they were created.

When issuing a Check Sheet, at least one mandatory item is required. Sign-off is blocked until all mandatory items are completed, no item is NOK, every completed item has independent QC verification and every required witness point is released. Optional items may remain pending.
