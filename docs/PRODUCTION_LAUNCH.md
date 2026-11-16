# OPERA — Production Launch Guide

**Product:** OPERA Commissioning, Pre-Commissioning & Start-up  
**Schema head:** 20261116_0019

This guide describes the production deployment of OPERA. It deliberately contains no shared demo credentials and no automatic demo-user seeding.

## 1. Production architecture

```text
Internet
  |
Nginx (TLS, ports 80/443)
  |
Gunicorn / Flask OPERA
  |-- PostgreSQL 16 (private network, persistent volume)
  |-- Redis 7 (rate-limit storage)
  '-- Docker secrets (database password and TLS key material)
```

## 2. Pre-flight

### Environment and secrets
1. Copy `.env.prod.example` to `.env.prod`.
2. Generate a unique Flask secret:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
3. Create secret files; never commit them:
   ```bash
   mkdir -p secrets
   openssl rand -base64 48 > secrets/postgres_password
   # Install the real TLS certificate and private key as:
   # secrets/tls_cert
   # secrets/tls_key
   chmod 600 secrets/postgres_password secrets/tls_key
   ```
4. Set a unique production database name and user in `.env.prod`.
5. Set the canonical HTTPS origin in `PUBLIC_BASE_URL`.
6. Configure SMTP only if account-recovery email is enabled. Use a verified `MAIL_FROM`.
7. Confirm `FLASK_ENV=production`, `SESSION_COOKIE_SECURE=true`, and Redis-backed rate limiting.

### Domain and TLS
- Point DNS A/AAAA records to the deployment host.
- Install a valid certificate and key in the Docker secret paths above.
- Verify Nginx TLS configuration before exposing ports 80/443.

### Database and migration
- Confirm `flask --app wsgi db heads` reports exactly one head: `20261116_0019`.
- Review the full Alembic chain. OPERA migration `20261116_0019` creates OPERA-owned tables and follows the inherited `20261017_0018` revision.
- Take a verified backup before upgrading any existing database.
- Test the migration on a staging copy first. Never stamp an existing database until its actual schema has been inspected.

## 3. Deploy

```bash
cp .env.prod.example .env.prod
# Edit .env.prod and install secret files before continuing.
./scripts/prod_up.sh build
./scripts/prod_up.sh up
./scripts/prod_up.sh migrate
./scripts/prod_up.sh status
```

The production helper intentionally has no demo-seed command. Do not seed sample accounts or predictable passwords into production.

## 4. Health checks

```bash
curl -fsS https://YOUR_DOMAIN/health/live
curl -fsS https://YOUR_DOMAIN/health/ready
curl -fsS https://YOUR_DOMAIN/metrics
```

All public routes must use HTTPS. Confirm HSTS, secure cookies, JSON logs, request IDs and Redis connectivity.

## 5. Staging acceptance scenario

Use separate real accounts for the following project roles:
1. Commissioning Manager
2. Commissioning Engineer
3. QC Inspector
4. Client Representative
5. Operations Lead

Run one full scenario:
1. Create a project, system and subsystem.
2. Assign members and confirm that users from another organization cannot access the project.
3. Create and issue a check sheet; record actual results.
4. Verify OK/N/A items with a QC user different from the operator.
5. Schedule a required Witness/Hold point, record notification, attendance and release.
6. Record contractor and client sign-offs using two different users.
7. Confirm that the signed-off check sheet and its items cannot be edited; create a new revision for corrections.
8. Raise, assign, close and verify Punch items. Confirm Category A/B items block MC.
9. Complete MC, RF, RFSU and operations acceptance gates.
10. Save a progress snapshot and verify the audit trail.

The electronic sign-off in this release is an authenticated, auditable acknowledgement. It is not a qualified PKI signature or a legal digital-signature certificate.

## 6. Backups and recovery

- Schedule `bash scripts/backup_postgres.sh` daily.
- Copy encrypted backups off-host and retain their SHA-256 files.
- Test restores into a new isolated database using `bash scripts/restore_postgres.sh BACKUP.dump opera_restore_test`.
- Never restore over the production database.
- Document the rollback image and database recovery process. Do not automatically downgrade the Alembic schema.

## 7. Go-live gate

Production launch is approved only when:
- [ ] Latest GitHub Actions run is fully green (quality, PostgreSQL integration, Docker and Trivy).
- [ ] Staging migration and acceptance scenario pass.
- [ ] Backup and isolated restore are verified.
- [ ] HTTPS, secure cookies, Redis, logs, monitoring and alerts are verified.
- [ ] Organization and project role boundaries are tested.
- [ ] Operations owner signs off on the workflow and handover rules.

No production migration, demo seed or deployment is performed by this repository change.
