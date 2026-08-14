#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODE="${1:-}"
readonly MASTER_PASSWORD="${ODOO_MASTER_PASSWORD:?ODOO_MASTER_PASSWORD is required}"
readonly DATABASE_HOST="${HOST:?HOST is required}"
readonly DATABASE_PORT="${PORT:?PORT is required}"
readonly DATABASE_USER="${USER:?USER is required}"
readonly DATABASE_PASSWORD="${PASSWORD:?PASSWORD is required}"
readonly DATABASE_NAME="${ODOO_DB_NAME:?ODOO_DB_NAME is required}"
readonly BASE_CONFIG=/etc/odoo/odoo.conf
readonly RUNTIME_CONFIG=/tmp/pent-odoo.conf

if [[ ! $DATABASE_NAME =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "ODOO_DB_NAME may contain only letters, digits and underscores." >&2
  exit 2
fi

umask 077
sed \
  -e '/^[[:space:]]*admin_passwd[[:space:]]*=/d' \
  -e '/^[[:space:]]*db_name[[:space:]]*=/d' \
  -e '/^[[:space:]]*dbfilter[[:space:]]*=/d' \
  "$BASE_CONFIG" >"$RUNTIME_CONFIG"
printf 'admin_passwd = %s\n' "$MASTER_PASSWORD" >>"$RUNTIME_CONFIG"
printf 'db_name = %s\n' "$DATABASE_NAME" >>"$RUNTIME_CONFIG"
printf 'dbfilter = ^%s$\n' "$DATABASE_NAME" >>"$RUNTIME_CONFIG"

case "$MODE" in
  bootstrap)
    export ODOO_RUNTIME_CONFIG="$RUNTIME_CONFIG"
    exec /usr/local/bin/pent-odoo-bootstrap
    ;;
  server)
    exec odoo server \
      --config="$RUNTIME_CONFIG" \
      --database="$DATABASE_NAME" \
      --db_host="$DATABASE_HOST" \
      --db_port="$DATABASE_PORT" \
      --db_user="$DATABASE_USER" \
      --db_password="$DATABASE_PASSWORD"
    ;;
  *)
    echo "Usage: pent-odoo-runtime bootstrap|server" >&2
    exit 2
    ;;
esac
