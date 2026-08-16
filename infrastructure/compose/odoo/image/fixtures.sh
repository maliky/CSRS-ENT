#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODE="${CSRS_E2E_MODE:-status}"
readonly DATASET="${CSRS_E2E_DATASET:-e2e-preprod}"
readonly DRY_RUN="${CSRS_E2E_DRY_RUN:-true}"
readonly ODOO_CONFIG="${ODOO_RUNTIME_CONFIG:?ODOO_RUNTIME_CONFIG is required}"
readonly DATABASE_NAME="${ODOO_DB_NAME:?ODOO_DB_NAME is required}"
readonly DATABASE_HOST="${HOST:?HOST is required}"
readonly DATABASE_PORT="${PORT:?PORT is required}"
readonly DATABASE_USER="${USER:?USER is required}"
readonly DATABASE_PASSWORD="${PASSWORD:?PASSWORD is required}"
readonly FIXTURE_PASSWORD="${CSRS_E2E_FIXTURE_PASSWORD:-}"

if [[ ! "$MODE" =~ ^(status|seed|clean|reseed)$ ]]; then
  echo "CSRS_E2E_MODE doit valoir status, seed, clean ou reseed." >&2
  exit 2
fi
if [[ ! "$DATASET" =~ ^e2e-[a-z0-9-]{1,40}$ ]]; then
  echo "CSRS_E2E_DATASET doit respecter le format e2e-nom-en-minuscules." >&2
  exit 2
fi
if [[ "$DRY_RUN" != true && "$DRY_RUN" != false ]]; then
  echo "CSRS_E2E_DRY_RUN doit valoir true ou false." >&2
  exit 2
fi
if [[ "$MODE" != status && "$DRY_RUN" == false ]]; then
  if [[ "${CSRS_E2E_CONFIRM_DATABASE:-}" != "$DATABASE_NAME" ]]; then
    echo "Refus de modifier une base non confirmée." >&2
    exit 2
  fi
fi
if [[ "$MODE" =~ ^(seed|reseed)$ && "$DRY_RUN" == false && ${#FIXTURE_PASSWORD} -lt 16 ]]; then
  echo "CSRS_E2E_FIXTURE_PASSWORD doit contenir au moins 16 caractères." >&2
  exit 2
fi

export CSRS_E2E_MODE="$MODE"
export CSRS_E2E_DATASET="$DATASET"
export CSRS_E2E_DRY_RUN="$DRY_RUN"

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

mode = os.environ["CSRS_E2E_MODE"]
dry_run = os.environ["CSRS_E2E_DRY_RUN"] == "true"
report = env["csrs.e2e.fixture"]._execute(
    mode,
    os.environ["CSRS_E2E_DATASET"],
    password=os.environ.get("CSRS_E2E_FIXTURE_PASSWORD"),
    dry_run=dry_run,
)
if mode != "status" and not dry_run:
    env.cr.commit()
else:
    env.cr.rollback()
print(json.dumps(report, ensure_ascii=True, sort_keys=True))
PYTHON
