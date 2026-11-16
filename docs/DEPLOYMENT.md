# Production Deployment Guide

## Architecture
Internet traffic terminates at Nginx. Nginx forwards traffic to Gunicorn/Flask over the private Docker network. PostgreSQL and Redis are internal services. Evidence files are stored in a dedicated persistent Docker volume mounted at `/app/instance/uploads`; they are never served from a public static directory.

## Required configuration
Copy .env.prod.example to a real .env.prod file and fill in production values.
Create these Docker secret files outside Git:
- secrets/postgres_password
- secrets/tls_cert
- secrets/tls_key

## Start
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d

Then inspect:
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs --tail=200 web
docker compose -f docker-compose.production.yml logs --tail=200 nginx

## Migration
Review the current Alembic history before the first production upgrade. If the existing database was created outside Alembic, establish the correct baseline first. After the baseline is confirmed:
docker compose -f docker-compose.production.yml exec web flask db upgrade

## Health checks
/health/live must return HTTP 200 when the process is alive.
/health/ready must return HTTP 200 only when required dependencies are ready and HTTP 503 when a required dependency is unavailable.

## Rollback
For an application-only rollback, stop deployment traffic, deploy the previous known-good image, confirm liveness/readiness, test login and a representative business workflow, then re-enable traffic.
Do not automatically downgrade database migrations. Use a reviewed migration or verified backup/restore procedure.

## Backups
Back up PostgreSQL on a schedule appropriate to business requirements. A backup is not operationally valid until a restore has been tested.

The backup script creates a PostgreSQL dump and a separate archive of the evidence volume, each with a SHA-256 file. Restore both as a matched pair. At minimum test schema restoration, representative commissioning records, evidence download, application startup, login/2FA, and a full commissioning workflow.

## Production acceptance
Production acceptance requires successful real-environment verification of TLS, PostgreSQL, Redis, migrations, authentication/2FA/RBAC, tenant isolation, Excel import/export, backup/restore, monitoring and graceful shutdown.

## Vercel and production boundary

The Git-linked Vercel project may be used for preview builds, but it is not the production runtime for this release. OPERA evidence uploads require persistent private storage, which the Docker Compose production stack provides through the `opera_uploads` volume. Vercel function filesystems are not a substitute for that persistent evidence store.

Database migrations must never run as part of a Vercel build. The repository therefore leaves Vercel's build command to its normal framework detection. For production, use the Docker Compose deployment above and apply migrations only after a verified backup. A Vercel production deployment would require separately configured PostgreSQL credentials, a strong `SECRET_KEY`, durable object storage, and an explicit migration/release process.
