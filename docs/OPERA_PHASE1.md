# OPERA Product Scope and Workflow Architecture

OPERA is an independent Operations, Pre-commissioning and Commissioning Management product for industrial and EPC projects. It is not a procurement, warehouse, supplier, inventory or material-control application.

## Active application domains

- Project setup and project-scoped membership
- System, subsystem and equipment hierarchy
- Pre-commissioning and commissioning check sheets
- Item-level inspection results, QC verification, rejection and controlled revision
- Punch List creation, assignment, verification, waiver and audit history
- Witness, Hold and Review points
- Mechanical Completion, Ready for Commissioning, Ready for Start-up and operations handover gates
- Progress snapshots, audit evidence and project-scoped attachments

## Shared platform services

The application retains Flask, SQLAlchemy, Alembic, user accounts, password recovery, TOTP, CSRF, session management, rate limiting, logging, PostgreSQL configuration and tenant/company boundaries. These are shared platform services, separate from the retired business modules.

## Project data boundaries

OPERA workflow records are stored in the commissioning model layer and are scoped to a company and project. Project membership and role permissions are enforced by the commissioning access service. A user account's legacy global role does not grant project access by itself.

## Legacy database policy

The old procurement and warehouse routes, templates, forms and business blueprints have been removed. Historical model mappings and Alembic revisions are retained only to avoid accidental data loss and destructive schema drift during upgrades. They are not exposed as OPERA application features. No production table is dropped by this cleanup. See [Legacy database compatibility](LEGACY_DATA_COMPATIBILITY.md).
