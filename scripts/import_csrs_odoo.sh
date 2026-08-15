#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODE="${1:-}"
readonly SOURCE_FILE="${2:-}"
readonly ENV_FILE="${3:-.env}"
readonly COMPOSE_FILE=infrastructure/compose/compose.yaml

if [[ "$MODE" != dry-run && "$MODE" != apply ]]; then
  echo "Usage: $0 dry-run|apply FICHIER_JSON [FICHIER_ENV]" >&2
  exit 2
fi
if [[ ! -f "$SOURCE_FILE" ]]; then
  echo "Fichier source introuvable." >&2
  exit 2
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Fichier d'environnement introuvable." >&2
  exit 2
fi

docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm -T \
  -e CSRS_MIGRATION_MODE="$MODE" \
  -e CSRS_MIGRATION_STDIN=true \
  odoo-bootstrap /usr/local/bin/csrs-ent-odoo-runtime import <"$SOURCE_FILE"
