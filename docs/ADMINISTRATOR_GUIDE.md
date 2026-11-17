# OPERA Administrator Guide

## Tenant and account administration
OPERA reuses the existing organization/company account boundary. Do not change a user's company identity as a shortcut for granting access. Company-level administrators and project managers create projects; project roles are assigned independently.

## Project role administration
- Commissioning Manager: project and workflow administration.
- Commissioning Engineer: task/check-sheet preparation and execution.
- QC Inspector: independent verification and witness attendance.
- Client Representative: client-side review/sign-off.
- Operations Lead: handover acceptance.
- Viewer: read-only project access.

Review the server-side permission map in services/commissioning_access.py before changing role behavior. Only project managers with `project.manage` can update the project Readiness policy.

## Project data governance
1. Approve project, system and subsystem coding conventions.
2. Approve equipment/tag import mappings.
3. Approve activity taxonomy and discipline catalog.
4. Approve Punch categories and definitions from the contract.
5. Approve Check Sheet templates, required types per milestone, acceptance criteria and witness requirements.
6. Configure the project Readiness policy for Punch blockers, required Check Sheet types, Hold-point gates and RFSU task completion. Record the approved procedure/revision and review changes through engineering/client governance.
7. Approve progress weights and denominators before publishing KPIs.
8. Confirm retention, backup and restoration policy for evidence attachments.

## Database operations
Back up PostgreSQL before applying migrations. Run migrations through the deployment migration procedure, not during an unreviewed application startup. Review the Alembic heads and current revision.

## Evidence storage
The current upload service writes to a local path. On Vercel/serverless, /tmp is ephemeral. Do not use this local adapter for production evidence retention until a durable private object-storage adapter is configured, access-controlled, backed up and restore-tested.

## Security
Use unique production secrets, HTTPS, least privilege and separate client/contractor accounts. Review audit events after privileged changes. Never put credentials, API tokens or recovery codes in project files or Git.


## Readiness policy
Use **Commissioning Operations → Readiness policy** to configure the MC, RFC and RFSU blockers. See [READINESS_POLICY.md](READINESS_POLICY.md) for the controls, OPERA defaults, fail-closed behavior and approval requirements. A saved configuration is not a substitute for approval under the project's completion procedure.


## Configurable subsystem dossier index
Project administrators can define mandatory document types, disciplines, minimum counts, approval requirements and evidence requirements from the Commissioning Operations page. Rules are audited and evaluated against current document revisions. See [DOSSIER_INDEX.md](DOSSIER_INDEX.md) for matching, default behavior and limitations.


## Preservation management
Project managers configure preservation plans only from approved project/OEM procedures. Inspectors record compliant/non-compliant/not-applicable outcomes, findings, environmental conditions, corrective actions and evidence. Inspection records are append-only. See [PRESERVATION_GUIDE.md](PRESERVATION_GUIDE.md) for workflow and limitations.


## Durable evidence storage

OPERA supports a private S3-compatible object-storage backend for commissioning evidence. For Vercel/serverless deployments, configure \`OPERA_STORAGE_BACKEND=s3\`, \`OPERA_S3_BUCKET\`, and \`OPERA_S3_REGION\`. For S3-compatible providers that require a custom endpoint, set \`OPERA_S3_ENDPOINT_URL\`. Provide \`OPERA_S3_ACCESS_KEY_ID\` and \`OPERA_S3_SECRET_ACCESS_KEY\` only when the provider does not support the deployment's IAM role. \`OPERA_S3_PREFIX\` defaults to \`opera-evidence\`. OPERA requests server-side AES-256 encryption for each uploaded object.

Keep the bucket private, enable provider-side versioning/retention as required, and configure independent backups. Never expose bucket credentials to browser code. Local storage remains available for persistent development installations; uploads are rejected with HTTP 503 when local storage is selected in a serverless runtime.

Before switching an existing installation to S3, copy existing evidence objects to the bucket, preserve each database row's \`storage_key\`, and verify the stored SHA-256 checksums after migration.


## Subsystem dossier export controls

The subsystem dossier page provides a printable PDF and a ZIP package containing a JSON manifest and linked evidence. The ZIP export verifies every evidence object's SHA-256 checksum and refuses to produce a package if an object is missing or mismatched. The default maximum declared evidence size is 100 MiB; configure OPERA_DOSSIER_EXPORT_MAX_BYTES to change the limit.

These are point-in-time working exports only. Do not use them as issued or approved contractual dossiers. A controlled dossier revision register, reviewer/approver workflow and formal issue record are not yet implemented.
