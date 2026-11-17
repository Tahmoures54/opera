# Legacy database retirement

OPERA keeps only the shared identity tables and the public demo-inquiry table from
the former application model layer. The active commissioning domain is registered
from `models_commissioning.py`.

## Retained tables

- `user`: shared authentication identity referenced by commissioning records.
- `account_recovery_token`: short-lived, single-use authenticator recovery.
- `contact_inquiry`: public demo/contact form submissions.

## Retired MaterialHub tables

The guarded migration `20261117_0019` removes the unused procurement, material,
supplier, purchase-order, delivery, receiving, quality, warehouse, approval,
tender/bid, report-sharing, material-request and old generic project tables.
It also removes the obsolete `user.project_id` and `user.store_name` columns.

The migration first checks every legacy table for rows. If any legacy table contains
records, it aborts before dropping tables. It also refuses to remove the two obsolete
user columns if either contains a non-null value. This is an intentional fail-safe:
export and review unexpected data rather than silently discard it.

## Operational requirements

- Take a verified PostgreSQL backup before applying migrations.
- Run `flask db upgrade` through the normal deployment migration process.
- If the migration aborts because legacy rows or user-column values exist, stop and
  export/review those records; do not bypass the guard.
- Historical Alembic revisions remain immutable. The downgrade for this retirement
  migration intentionally refuses to recreate empty legacy tables; restore from backup
  if rollback is required.
