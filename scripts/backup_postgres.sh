#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env.prod ]]; then
  echo "Missing .env.prod" >&2
  exit 1
fi

umask 077
mkdir -p backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="backups/opera_${stamp}.dump"
tmp="${backup}.tmp"
evidence="backups/opera_evidence_${stamp}.tar.gz"
evidence_tmp="${evidence}.tmp"
if [[ -e "$backup" || -e "${backup}.sha256" || -e "$evidence" || -e "${evidence}.sha256" ]]; then
  echo "Backup path already exists; refusing to overwrite: $backup" >&2
  exit 1
fi
trap 'rm -f "$tmp" "${tmp}.sha256" "$evidence_tmp" "${evidence_tmp}.sha256"' EXIT
docker compose --env-file .env.prod -f docker-compose.production.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$tmp"
if [[ ! -s "$tmp" ]]; then
  echo "pg_dump returned an empty backup" >&2
  exit 1
fi
sha256sum "$tmp" | awk '{print $1}' > "${tmp}.sha256"
mv "$tmp" "$backup"
mv "${tmp}.sha256" "${backup}.sha256"

# Evidence files live in a separate persistent Docker volume and must be backed up
# alongside PostgreSQL so attachment metadata and file bytes remain consistent.
docker compose --env-file .env.prod -f docker-compose.production.yml run --rm --no-deps \
  --entrypoint sh web -c 'tar -czf - -C /app/instance/uploads .' > "$evidence_tmp"
if [[ ! -s "$evidence_tmp" ]]; then
  echo "Evidence volume backup is empty" >&2
  exit 1
fi
sha256sum "$evidence_tmp" | awk '{print $1}' > "${evidence_tmp}.sha256"
mv "$evidence_tmp" "$evidence"
mv "${evidence_tmp}.sha256" "${evidence}.sha256"
trap - EXIT
echo "Database backup: $backup"
echo "Database SHA-256: ${backup}.sha256"
echo "Evidence backup: $evidence"
echo "Evidence SHA-256: ${evidence}.sha256"
