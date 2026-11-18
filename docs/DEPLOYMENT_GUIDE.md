# OPERA Deployment Guide (authoritative)

This is the **only** deployment guide for OPERA. The production target is the
Docker Compose stack in `docker-compose.production.yml`. Earlier guidance that
described Vercel as the production runtime has been removed. See
[Production boundary](#production-boundary).

Related documents:

- `docs/PRODUCTION_LAUNCH.md`: staging acceptance scenario and go-live gate.
- `docs/ADMINISTRATOR_GUIDE.md`: evidence-storage configuration.

## 1. Production target

```text
Internet -> Nginx (TLS, 80/443) -> Gunicorn/Flask (web, 8000, private network)
                                    |-- PostgreSQL 16 (postgres_data volume)
                                    |-- Redis 7 (rate-limit storage, redis_data volume)
                                    '-- Evidence files (opera_uploads volume, /app/instance/uploads)
```

Evidence files are never served from a public static directory. Downloads go
through authorization checks.

## 2. Runtime requirements

- Docker Engine with the Compose plugin.
- A host with a stable DNS name and a valid TLS certificate.
- PostgreSQL 16 for all production data. The production image contains no SQLite runtime.
- A `SECRET_KEY` of at least 32 bytes, generated per environment.
- Secure cookies (`SESSION_COOKIE_SECURE=true`) and HTTPS only.

## 3. Secrets and configuration

1. Copy the template and fill in production values:

   ```bash
   cp .env.prod.example .env.prod
   python -c "import secrets; print(secrets.token_hex(32))"   # paste into SECRET_KEY
   ```

2. Create Docker secret files outside Git. Never commit them:

   ```bash
   mkdir -p secrets
   openssl rand -base64 48 > secrets/postgres_password
   # Install the real certificate and key as secrets/tls_cert and secrets/tls_key
   chmod 600 secrets/postgres_password secrets/tls_key
   ```

3. Confirm in `.env.prod`:
   - `FLASK_ENV=production`
   - `PUBLIC_BASE_URL` set to the canonical HTTPS origin
   - `SESSION_COOKIE_SECURE=true`
   - Redis-backed rate limiting enabled
   - SMTP settings only if account-recovery email is enabled, with a verified `MAIL_FROM`

## 4. Database and migrations

- Current Alembic head: **`20261117_0033`**. Verify it before any upgrade:

  ```bash
  docker compose -f docker-compose.production.yml exec web flask --app wsgi db heads
  ```

  The command must print exactly one head.

- Take a verified PostgreSQL backup before any upgrade (section 7).
- Test the upgrade on a staging copy first.
- Never stamp an existing database until its actual schema has been inspected.
- Migrations are run as a separate, controlled release step. **Never run them in a build command.**

## 5. Deploy

```bash
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml exec web flask --app wsgi db upgrade
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs --tail=200 web
docker compose -f docker-compose.production.yml logs --tail=200 nginx
```

`scripts/prod_up.sh` wraps the same commands (`build`, `up`, `migrate`, `status`).
It contains no demo-seed step. Do not seed sample accounts or predictable passwords into production.

## 6. Health checks

| Endpoint | Expected |
|---|---|
| `/health/live` | HTTP 200 when the process is alive |
| `/health/ready` | HTTP 200 when PostgreSQL and Redis are reachable; HTTP 503 otherwise |
| `/metrics` | Prometheus metrics; restrict access at the network or Nginx layer |

```bash
curl -fsS https://YOUR_DOMAIN/health/live
curl -fsS https://YOUR_DOMAIN/health/ready
```

Confirm HSTS, secure cookies, request IDs and log output after each deploy.

## 7. Backups and restore

- Run `bash scripts/backup_postgres.sh` daily. It writes:
  - a PostgreSQL custom-format dump with a `.sha256` file, and
  - an archive of the `opera_uploads` evidence volume with its own `.sha256` file.
- Copy both off-host. Restore them as a matched pair.
- Test restores into an isolated database and volume. Never restore over production:

  ```bash
  bash scripts/restore_postgres.sh BACKUP.dump opera_restore_test
  ```

- A backup is not operationally valid until a restore has been tested, including schema, representative records, evidence download, login with 2FA and a complete workflow.

## 8. Rollback

- For an application-only rollback, redeploy the previous known-good image, confirm liveness and readiness, and test login and one workflow before re-enabling traffic.
- **Do not automatically downgrade database migrations.** Use a reviewed migration or a verified backup restore.

## 9. Release checklist

1. Confirm the exact `main` commit and the open PR list.
2. Confirm every CI job passed for that commit (quality, PostgreSQL integration, Docker and Trivy).
3. Back up PostgreSQL and the evidence volume.
4. Run the migration and verify `alembic_version` shows `20261117_0033`.
5. Deploy the same commit.
6. Run `/health/live` and `/health/ready`.
7. Run the acceptance scenario in `docs/PRODUCTION_LAUNCH.md` with approved non-production data.
8. Confirm logs, backups and evidence storage.
9. Record the rollback reference (previous image and backup name).

## Production boundary

OPERA has two supported production targets. Both must meet the same requirements.

1. **Vercel (owner-selected production target).** Follow section 10. The Vercel project `tahmoures54s-projects/opera` builds previews from GitHub. Production is **not verified** until every step in section 10 is complete.
2. **Docker Compose (self-hosted alternative).** Sections 1 to 9 describe this path.

Requirements for either target:

- PostgreSQL for all production data. SQLite is rejected in production.
- Durable private evidence storage. On Vercel, the local filesystem is not durable, and the application refuses local evidence storage in serverless mode. Use the S3-compatible backend (section 10).
- Migrations run as a controlled release step, never in a build command. `vercel.json` must not contain a `buildCommand` that migrates.
- A verified backup and restore of PostgreSQL and evidence storage before any production change.

## 10. Vercel production runbook

### 10.1 Environment variables (set in the Vercel project, Production scope only)

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | At least 32 bytes, generated per environment |
| `DATABASE_URL` | PostgreSQL connection string (a `postgres://` alias is accepted) |
| `PUBLIC_BASE_URL` | Canonical HTTPS origin |
| `SESSION_COOKIE_SECURE` | `true` |
| `OPERA_STORAGE_BACKEND` | `s3` |
| `OPERA_S3_BUCKET` | Private bucket for evidence |
| `OPERA_S3_REGION` | Bucket region |
| `OPERA_S3_ENDPOINT_URL` | Only for S3-compatible providers that need a custom endpoint |
| `OPERA_S3_ACCESS_KEY_ID`, `OPERA_S3_SECRET_ACCESS_KEY` | Only if the provider does not support an IAM role |
| `OPERA_S3_PREFIX` | Optional; defaults to `opera-evidence` |
| `RATELIMIT_STORAGE_URI` | Redis URL for shared rate limiting (required for multi-instance serverless) |
| `ADMIN_EMAIL` | Optional; the account with this email gets administrator rights at registration |

Do not set `VERCEL_ENV` manually. Vercel sets it.

### 10.2 Migrations

1. Take a verified PostgreSQL backup.
2. Confirm the target database is the intended production database.
3. Run `VERCEL_ENV=production python scripts/vercel_migrate.py` from a controlled release environment, not from a build.
4. Confirm `flask --app wsgi db current` shows `20261118_0035` (or the current head).

### 10.3 Deploy and verify

1. Deploy the exact commit from `main` to Production in Vercel.
2. Record the deployment URL and commit SHA.
3. Check `/health/live` and `/health/ready`. Readiness must return 200.
4. Upload a test evidence file to a non-production project, download it, and confirm its SHA-256 matches.
5. Run the acceptance scenario in `docs/PRODUCTION_LAUNCH.md` with approved non-production data.
6. Only then record the deployment as verified.

### 10.4 Rollback

Redeploy the previous Vercel deployment. Do not downgrade migrations automatically. Use a verified backup restore if data must be reverted.

### 10.5 Status

Vercel production is **not verified** by this document. The current Vercel preview build for `main` succeeded, but no production deployment, production migration or S3 round-trip has been confirmed.

## Status of this document

This guide describes configuration that exists in the repository. Production deployment has **not** been verified in this document. Verification requires a real deployment, a deployed commit and a passing acceptance run.
