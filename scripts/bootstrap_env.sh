#!/usr/bin/env bash
set -Eeuo pipefail

readonly OUTPUT_FILE="${1:-.env}"

if [[ -e "$OUTPUT_FILE" ]]; then
  echo "Refus d'écraser $OUTPUT_FILE." >&2
  exit 2
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl est requis pour générer les secrets." >&2
  exit 1
fi

umask 077
django_secret=$(openssl rand -base64 48 | tr -d '\n')
odoo_db_password=$(openssl rand -base64 36 | tr -d '\n')
odoo_master_password=$(openssl rand -base64 36 | tr -d '\n')
odoo_admin_password=$(openssl rand -base64 36 | tr -d '\n')

sed \
  -e "s|^DJANGO_SECRET_KEY=.*$|DJANGO_SECRET_KEY=$django_secret|" \
  -e "s|^ODOO_DB_PASSWORD=.*$|ODOO_DB_PASSWORD=$odoo_db_password|" \
  -e "s|^ODOO_MASTER_PASSWORD=.*$|ODOO_MASTER_PASSWORD=$odoo_master_password|" \
  -e "s|^ODOO_ADMIN_PASSWORD=.*$|ODOO_ADMIN_PASSWORD=$odoo_admin_password|" \
  .env.example >"$OUTPUT_FILE"

chmod 0600 "$OUTPUT_FILE"
echo "Environnement créé dans $OUTPUT_FILE (mode 0600)."
