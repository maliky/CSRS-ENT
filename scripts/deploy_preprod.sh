#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ENV_FILE="${1:-${ROOT_DIR}/../config/.env}"
readonly COMPOSE_FILE="${ROOT_DIR}/infrastructure/compose/compose.yaml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Fichier d'environnement introuvable : $ENV_FILE" >&2
  exit 2
fi

cd "$ROOT_DIR"
docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet
docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build odoo-bootstrap django
docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up odoo-bootstrap
docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d odoo django redis mailpit
docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
