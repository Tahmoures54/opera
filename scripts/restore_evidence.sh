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
# Reject absolute paths and parent traversal before extraction.
while IFS= read -r entry; do
  case "$entry" in
    /*|..|../*|*/../*) echo "Unsafe archive path: $entry" >&2; exit 1 ;;
  esac
done < <(tar -tzf "$archive")

echo "Restoring evidence into the OPERA uploads volume. Stop application writes first."
docker compose --env-file .env.prod -f docker-compose.production.yml run --rm --no-deps \
  --entrypoint sh web -c 'tar -xzf - -C /app/instance/uploads' < "$archive"
echo "Evidence restore completed. Verify file access before re-enabling traffic."
