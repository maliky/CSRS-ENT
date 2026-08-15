#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODE="${CSRS_MIGRATION_MODE:-dry-run}"
readonly ODOO_CONFIG="${ODOO_RUNTIME_CONFIG:?ODOO_RUNTIME_CONFIG is required}"
readonly DATABASE_NAME="${ODOO_DB_NAME:?ODOO_DB_NAME is required}"
readonly DATABASE_HOST="${HOST:?HOST is required}"
readonly DATABASE_PORT="${PORT:?PORT is required}"
readonly DATABASE_USER="${USER:?USER is required}"
readonly DATABASE_PASSWORD="${PASSWORD:?PASSWORD is required}"

source_file="${CSRS_MIGRATION_FILE:-/run/csrs-ent-migration/csrs.json}"
temporary_source=""
success_file=$(mktemp /tmp/csrs-ent-csrs-import-success.XXXXXX)

cleanup() {
  if [[ -n "$temporary_source" ]]; then
    rm -f "$temporary_source"
  fi
  rm -f "$success_file"
}
trap cleanup EXIT

if [[ "${CSRS_MIGRATION_STDIN:-false}" == true ]]; then
  umask 077
  source_file=$(mktemp /tmp/csrs-ent-csrs-migration.XXXXXX.json)
  temporary_source="$source_file"
  dd of="$source_file" status=none
fi

if [[ "$MODE" != dry-run && "$MODE" != apply ]]; then
  echo "CSRS_MIGRATION_MODE doit valoir dry-run ou apply." >&2
  exit 2
fi
if [[ ! -r "$source_file" ]]; then
  echo "Le fichier de migration est absent ou illisible." >&2
  exit 2
fi

export CSRS_MIGRATION_FILE="$source_file"
export CSRS_MIGRATION_MODE="$MODE"
export CSRS_MIGRATION_SUCCESS_FILE="$success_file"

odoo shell \
  --config="$ODOO_CONFIG" \
  --database="$DATABASE_NAME" \
  --db_host="$DATABASE_HOST" \
  --db_port="$DATABASE_PORT" \
  --db_user="$DATABASE_USER" \
  --db_password="$DATABASE_PASSWORD" \
  --no-http <<'PYTHON'
import json
import os

with open(os.environ["CSRS_MIGRATION_FILE"], encoding="utf-8") as source:
    payload = json.load(source)

apply = os.environ["CSRS_MIGRATION_MODE"] == "apply"
report = env["csrs.migration.importer"].import_payload(payload, apply=apply)
if apply:
    env.cr.commit()
else:
    env.cr.rollback()
print(json.dumps(report, ensure_ascii=True, sort_keys=True))
with open(os.environ["CSRS_MIGRATION_SUCCESS_FILE"], "w", encoding="ascii") as marker:
    marker.write("ok")
PYTHON

if [[ ! -s "$success_file" ]]; then
  echo "L'import Odoo n'a pas atteint son point de validation." >&2
  exit 1
fi
