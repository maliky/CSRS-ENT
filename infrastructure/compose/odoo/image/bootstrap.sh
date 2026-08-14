#!/usr/bin/env bash
set -Eeuo pipefail

readonly DATABASE_HOST="${HOST:?HOST is required}"
readonly DATABASE_PORT="${PORT:?PORT is required}"
readonly DATABASE_USER="${USER:?USER is required}"
readonly DATABASE_PASSWORD="${PASSWORD:?PASSWORD is required}"
readonly DATABASE_NAME="${ODOO_DB_NAME:?ODOO_DB_NAME is required}"
readonly ADMIN_LOGIN="${ODOO_ADMIN_LOGIN:?ODOO_ADMIN_LOGIN is required}"
readonly ADMIN_PASSWORD="${ODOO_ADMIN_PASSWORD:?ODOO_ADMIN_PASSWORD is required}"
readonly ODOO_CONFIG="${ODOO_RUNTIME_CONFIG:?ODOO_RUNTIME_CONFIG is required}"

if [[ ${#ADMIN_PASSWORD} -lt 16 ]]; then
  echo "ODOO_ADMIN_PASSWORD must contain at least 16 characters." >&2
  exit 2
fi

export PGPASSWORD="$DATABASE_PASSWORD"

for _ in $(seq 1 60); do
  if pg_isready --host "$DATABASE_HOST" --port "$DATABASE_PORT" --username "$DATABASE_USER" --dbname "$DATABASE_NAME" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! pg_isready --host "$DATABASE_HOST" --port "$DATABASE_PORT" --username "$DATABASE_USER" --dbname "$DATABASE_NAME" >/dev/null 2>&1; then
  echo "Odoo PostgreSQL did not become ready in time." >&2
  exit 1
fi

module_table=$(psql --host "$DATABASE_HOST" --port "$DATABASE_PORT" --username "$DATABASE_USER" --dbname "$DATABASE_NAME" --tuples-only --no-align --command "SELECT to_regclass('public.ir_module_module') IS NOT NULL")

if [[ $module_table != t ]]; then
  echo "Initializing Odoo and the CSRS reporting module without demo data."
  odoo server \
    --config="$ODOO_CONFIG" \
    --database="$DATABASE_NAME" \
    --db_host="$DATABASE_HOST" \
    --db_port="$DATABASE_PORT" \
    --db_user="$DATABASE_USER" \
    --db_password="$DATABASE_PASSWORD" \
    --init=csrs_reporting \
    --without-demo=true \
    --stop-after-init
else
  echo "Updating the CSRS reporting module."
  odoo server \
    --config="$ODOO_CONFIG" \
    --database="$DATABASE_NAME" \
    --db_host="$DATABASE_HOST" \
    --db_port="$DATABASE_PORT" \
    --db_user="$DATABASE_USER" \
    --db_password="$DATABASE_PASSWORD" \
    --update=csrs_reporting \
    --without-demo=true \
    --stop-after-init
fi

export ODOO_ADMIN_LOGIN="$ADMIN_LOGIN"
export ODOO_ADMIN_PASSWORD="$ADMIN_PASSWORD"

odoo shell \
  --config="$ODOO_CONFIG" \
  --database="$DATABASE_NAME" \
  --db_host="$DATABASE_HOST" \
  --db_port="$DATABASE_PORT" \
  --db_user="$DATABASE_USER" \
  --db_password="$DATABASE_PASSWORD" \
  --no-http <<'PYTHON'
import os

module = env["ir.module.module"].search([("name", "=", "csrs_reporting")], limit=1)
if module.state != "installed":
    raise RuntimeError("The csrs_reporting module is not installed.")

admin = env.ref("base.user_admin")
if not admin.csrs_source_id:
    admin.write({
        "login": os.environ["ODOO_ADMIN_LOGIN"],
        "email": os.environ["ODOO_ADMIN_LOGIN"],
        "password": os.environ["ODOO_ADMIN_PASSWORD"],
    })
env.cr.commit()
PYTHON

echo "Odoo, csrs_reporting and the administrator are ready."
