# OPERA Deployment Guide

## Runtime requirements
- Python 3.12.
- PostgreSQL for production.
- A strong SECRET_KEY of at least 32 bytes.
- HTTPS and secure cookies.
- Persistent, private evidence storage.
- Scheduled database and evidence backups.

## Vercel
Configure the required environment variables in the Vercel project. Production must use PostgreSQL; SQLite is rejected by production configuration. Apply Alembic migrations through the repository's controlled migration script / CI release process. Do not add schema migrations to the Vercel build command.

## Evidence storage warning
The current services/commissioning_storage.py implementation uses a local filesystem path. Vercel serverless filesystem writes outside /tmp are not durable and /tmp is ephemeral. Before relying on production attachments, implement and configure a durable private object-storage adapter, then test upload, download authorization, backup and restore.

## Release checklist
1. Review the exact main commit and open PR list.
2. Confirm all CI jobs passed for the candidate commit.
3. Back up PostgreSQL and evidence storage.
4. Apply migrations and verify alembic_version.
5. Deploy the same commit to Production.
6. Verify Vercel reports Ready and the deployment commit matches main.
7. Run /health/live and /health/ready checks.
8. Sign in and verify a test project workflow using approved non-production test data.
9. Confirm logs, backups and evidence storage.
10. Retain rollback instructions and previous deployment reference.
