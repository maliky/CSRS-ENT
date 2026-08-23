#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly MODE="${1:-status}"
readonly DATASET="${2:-e2e-preprod}"
readonly ENV_FILE="${3:-${ROOT_DIR}/.env}"
readonly COMPOSE_FILE="${ROOT_DIR}/infrastructure/compose/compose.yaml"
readonly COMPOSE_PROJECT="${CSRS_E2E_COMPOSE_PROJECT_NAME:-}"
readonly SECRET_DIR="${CSRS_E2E_SECRET_DIR:-${ROOT_DIR}/secrets/e2e}"
readonly PASSWORD_FILE="${SECRET_DIR}/${DATASET}.password"

if [[ ! "$MODE" =~ ^(status|seed|clean|reseed)$ ]]; then
  echo "Usage : $0 status|seed|clean|reseed [e2e-jeu] [fichier-env]" >&2
  exit 2
fi
if [[ ! "$DATASET" =~ ^e2e-[a-z0-9-]{1,40}$ ]]; then
  echo "Le jeu doit respecter le format e2e-nom-en-minuscules." >&2
  exit 2
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Fichier d'environnement introuvable : $ENV_FILE" >&2
  exit 2
fi
if [[ -n "$COMPOSE_PROJECT" && ! "$COMPOSE_PROJECT" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]]; then
  echo "Nom de projet Compose de capture invalide." >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
: "${ODOO_DB_NAME:?ODOO_DB_NAME est requis dans le fichier environnement}"

dry_run=true
if [[ "${CSRS_E2E_APPLY:-false}" == true ]]; then
  dry_run=false
fi

if [[ "$MODE" =~ ^(seed|reseed)$ && "$dry_run" == false && -z "${CSRS_E2E_FIXTURE_PASSWORD:-}" ]]; then
  umask 077
  install -d -m 0700 "$SECRET_DIR"
  if [[ ! -s "$PASSWORD_FILE" ]]; then
    openssl rand -base64 24 >"$PASSWORD_FILE"
    chmod 0600 "$PASSWORD_FILE"
  fi
  IFS= read -r CSRS_E2E_FIXTURE_PASSWORD <"$PASSWORD_FILE"
  export CSRS_E2E_FIXTURE_PASSWORD
fi

cd "$ROOT_DIR"
compose=(docker-compose)
if [[ -n "$COMPOSE_PROJECT" ]]; then
  compose+=(-p "$COMPOSE_PROJECT")
fi
compose+=(--env-file "$ENV_FILE" -f "$COMPOSE_FILE")
"${compose[@]}" run --rm -T \
  -e CSRS_E2E_MODE="$MODE" \
  -e CSRS_E2E_DATASET="$DATASET" \
  -e CSRS_E2E_DRY_RUN="$dry_run" \
  -e CSRS_E2E_CONFIRM_DATABASE="${CSRS_E2E_CONFIRM_DATABASE:-}" \
  -e CSRS_E2E_FIXTURE_PASSWORD="${CSRS_E2E_FIXTURE_PASSWORD:-}" \
  odoo-bootstrap /usr/local/bin/csrs-ent-odoo-runtime fixtures
