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

cd "$ROOT_DIR/frontend"
exec npm run test:e2e -- "$@"
