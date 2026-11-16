#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env.prod ]]; then
  echo "Missing .env.prod" >&2
  exit 1
fi
if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo "Usage: $0 BACKUP_EVIDENCE.tar.gz" >&2
  exit 2
fi
archive="$(realpath "$1")"
if [[ ! -f "${archive}.sha256" ]]; then
  echo "Missing SHA-256 sidecar: ${archive}.sha256" >&2
  exit 1
fi
expected="$(tr -d '[:space:]' < "${archive}.sha256")"
actual="$(sha256sum "$archive" | awk '{print $1}')"
if [[ "$expected" != "$actual" ]]; then
  echo "Evidence backup checksum mismatch" >&2
  exit 1
fi
# Validate member paths and reject symlinks, hardlinks, and special files.
# GNU tar's name listing alone does not expose link targets.
python scripts/validate_evidence_archive.py "$archive"

echo "Restoring evidence into the OPERA uploads volume. Stop application writes first."
docker compose --env-file .env.prod -f docker-compose.production.yml run --rm --no-deps \
  --entrypoint sh web -c 'tar -xzf - -C /app/instance/uploads' < "$archive"
echo "Evidence restore completed. Verify file access before re-enabling traffic."
