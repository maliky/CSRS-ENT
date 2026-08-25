#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ENV_FILE="${1:-${ROOT_DIR}/.env}"
readonly SOURCE_SSH="${2:-jil@179.237.107.40}"
readonly LOCK_FILE="${CSRS_LEGACY_SYNC_LOCK:-/tmp/csrs-ent-legacy-sync.lock}"

test -f "$ENV_FILE"
exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "Une synchronisation CSRS Report est déjà en cours." >&2
  exit 3
}

readonly TEMP_DIR="$(mktemp -d -t csrs-ent-legacy-sync.XXXXXX)"
readonly PAYLOAD="${TEMP_DIR}/snapshot-v4.json"
trap 'rm -rf -- "$TEMP_DIR"' EXIT

cd "$ROOT_DIR"
./scripts/export_csrs_remote.sh "$SOURCE_SSH" "$PAYLOAD"
./scripts/import_csrs_odoo.sh dry-run "$PAYLOAD" "$ENV_FILE"
./scripts/import_csrs_odoo.sh reconcile "$PAYLOAD" "$ENV_FILE"
