#!/usr/bin/env bash
set -Eeuo pipefail

export PATH="/home/jil/.nvm/versions/node/v24.11.0/bin:/usr/local/bin:/usr/bin:/bin"

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ENV_FILE="${1:-${ROOT_DIR}/.env}"
readonly DATASET="e2e-manual"
readonly BASE_URL="${CSRS_MANUAL_BASE_URL:-http://127.0.0.1:18017}"
readonly SECRET_DIR="${CSRS_E2E_SECRET_DIR:-${ROOT_DIR}/secrets/e2e}"
readonly PASSWORD_FILE="${SECRET_DIR}/${DATASET}.password"

case "$BASE_URL" in
  http://127.0.0.1:* | http://localhost:*) ;;
  *)
    echo "Cible de capture refusée : utilisez uniquement localhost ou 127.0.0.1." >&2
    exit 2
    ;;
esac

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Fichier d'environnement introuvable : $ENV_FILE" >&2
  exit 2
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "npm et Node 24 sont requis pour produire les captures." >&2
  exit 2
fi
if ! curl --silent --fail --max-time 5 "$BASE_URL/app/" >/dev/null; then
  echo "L'instance locale ne répond pas sur $BASE_URL. Démarrez-la avant les captures." >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
: "${ODOO_DB_NAME:?ODOO_DB_NAME est requis dans le fichier environnement}"

if [[ -z "${CSRS_E2E_CONFIRM_DATABASE:-}" || "$CSRS_E2E_CONFIRM_DATABASE" != "$ODOO_DB_NAME" ]]; then
  echo "CSRS_E2E_CONFIRM_DATABASE doit correspondre exactement à la base locale." >&2
  exit 2
fi

seeded=false
cleanup() {
  status=$?
  if [[ "$seeded" == true ]]; then
    CSRS_E2E_APPLY=true \
      CSRS_E2E_CONFIRM_DATABASE="$ODOO_DB_NAME" \
      CSRS_E2E_SECRET_DIR="$SECRET_DIR" \
      "$ROOT_DIR/scripts/e2e_fixtures.sh" clean "$DATASET" "$ENV_FILE" || true
  fi
  if [[ -f "$PASSWORD_FILE" ]]; then
    rm -f "$PASSWORD_FILE"
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

CSRS_E2E_APPLY=true \
  CSRS_E2E_CONFIRM_DATABASE="$ODOO_DB_NAME" \
  CSRS_E2E_SECRET_DIR="$SECRET_DIR" \
  "$ROOT_DIR/scripts/e2e_fixtures.sh" reseed "$DATASET" "$ENV_FILE"
seeded=true

if [[ ! -s "$PASSWORD_FILE" || "$(stat -c '%a' "$PASSWORD_FILE")" != "600" ]]; then
  echo "Le mot de passe du jeu doit exister avec le mode 0600." >&2
  exit 2
fi
IFS= read -r CSRS_E2E_FIXTURE_PASSWORD <"$PASSWORD_FILE"
export CSRS_E2E_FIXTURE_PASSWORD
export CSRS_E2E_DATASET="$DATASET"
export CSRS_MANUAL_BASE_URL="$BASE_URL"

npm run manual:screenshots --prefix "$ROOT_DIR/frontend"

echo "Captures mises à jour dans docs/screenshots/."
