#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly SECRET_FILE="${CSRS_E2E_SECRET_FILE:-${ROOT_DIR}/.secrets}"
readonly NODE_BIN="${CSRS_E2E_NODE_BIN:-/home/jil/.nvm/versions/node/v24.11.0/bin}"

if [[ ! -x "$NODE_BIN/npm" ]]; then
  echo "npm 24 est introuvable dans $NODE_BIN." >&2
  exit 2
fi
if [[ -z "${CSRS_E2E_PASSWORD:-}" ]]; then
  if [[ ! -f "$SECRET_FILE" ]]; then
    echo "Définissez CSRS_E2E_PASSWORD ou fournissez un fichier secret local." >&2
    exit 2
  fi
  secret_mode="$(stat -c '%a' "$SECRET_FILE")"
  if [[ "$secret_mode" != 600 ]]; then
    echo "Le fichier secret doit avoir le mode 0600." >&2
    exit 2
  fi
  IFS= read -r CSRS_E2E_PASSWORD <"$SECRET_FILE"
  export CSRS_E2E_PASSWORD
fi

export PATH="$NODE_BIN:/usr/local/bin:/usr/bin:/bin"
export CSRS_E2E_BASE_URL="${CSRS_E2E_BASE_URL:-https://preprod.ent.koba.sarl}"
export CSRS_E2E_LOGIN="${CSRS_E2E_LOGIN:-dev}"

if [[ "${CSRS_E2E_MUTATIONS:-false}" == true ]]; then
  readonly DATASET="${CSRS_E2E_DATASET:-}"
  if [[ ! "$DATASET" =~ ^e2e-[a-z0-9-]{1,40}$ ]]; then
    echo "CSRS_E2E_DATASET doit respecter le format e2e-nom-en-minuscules." >&2
    exit 2
  fi
  readonly FIXTURE_SECRET_DIR="${CSRS_E2E_SECRET_DIR:-${ROOT_DIR}/secrets/e2e}"
  readonly FIXTURE_PASSWORD_FILE="${CSRS_E2E_FIXTURE_PASSWORD_FILE:-${FIXTURE_SECRET_DIR}/${DATASET}.password}"
  if [[ ! -f "$FIXTURE_PASSWORD_FILE" || "$(stat -c '%a' "$FIXTURE_PASSWORD_FILE")" != 600 ]]; then
    echo "Le mot de passe du jeu E2E doit exister avec le mode 0600." >&2
    exit 2
  fi
  IFS= read -r CSRS_E2E_FIXTURE_PASSWORD <"$FIXTURE_PASSWORD_FILE"
  if (( ${#CSRS_E2E_FIXTURE_PASSWORD} < 16 )); then
    echo "Le mot de passe du jeu E2E est invalide." >&2
    exit 2
  fi
  export CSRS_E2E_FIXTURE_PASSWORD
fi

cd "$ROOT_DIR/frontend"
exec npm run test:e2e -- "$@"
