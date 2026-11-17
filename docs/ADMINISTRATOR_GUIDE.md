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
