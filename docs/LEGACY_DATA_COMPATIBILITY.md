# Legacy database compatibility boundary

OPERA no longer registers or ships the inherited MaterialHub procurement, warehouse,
material marketplace, supplier, delivery, generic reporting, intelligence, or role-workspace
HTTP modules and their user-facing templates.

The historical `models.py` mappings and Alembic revision history are intentionally retained
for now. The baseline migration creates MaterialHub-era tables, and existing installations may
still contain records in those tables. Removing ORM mappings or dropping tables without a
production data inventory could cause destructive schema drift or data loss. No legacy-table
DROP migration is included in this cleanup.

OPERA's active product workflows use `models_commissioning.py`, the commissioning blueprints,
and the project-scoped access services. A later database retirement migration requires an
explicit inventory of production table usage, backup verification, and an approved retention
policy before any old table is dropped.
