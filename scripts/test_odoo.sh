#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ENV_FILE="${1:-${ROOT_DIR}/.env.example}"
readonly COMPOSE_FILE="${ROOT_DIR}/infrastructure/compose/compose.yaml"
readonly PROJECT_NAME="${CSRS_ENT_COMPOSE_PROJECT:-csrs_ent_ci_${GITHUB_RUN_ID:-local}}"

if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
elif docker-compose version >/dev/null 2>&1; then
  compose=(docker-compose)
else
  echo "Docker Compose est requis." >&2
  exit 1
fi

cleanup() {
  "${compose[@]}" -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "$ROOT_DIR"
"${compose[@]}" -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet
"${compose[@]}" -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build odoo-bootstrap
"${compose[@]}" -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up odoo-bootstrap
"${compose[@]}" -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm odoo-bootstrap /usr/local/bin/csrs-ent-odoo-runtime test
