#!/usr/bin/env bash
set -Eeuo pipefail

readonly SSH_TARGET="${1:-jil@179.237.107.40}"
readonly OUTPUT_FILE="${2:-}"
readonly SOURCE_PROJECT="${CSRS_REMOTE_PROJECT:-/home/jil/csrs_report}"
readonly REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly EXPORT_SCRIPT="${REPOSITORY_ROOT}/scripts/export_csrs_source.py"

if [[ -z $OUTPUT_FILE ]]; then
  echo "Usage: $0 [CIBLE_SSH] FICHIER_JSON" >&2
  exit 2
fi
if [[ -e $OUTPUT_FILE ]]; then
  echo "Le fichier de destination existe déjà." >&2
  exit 2
fi

umask 077
readonly TEMP_FILE="$(mktemp "${OUTPUT_FILE}.tmp.XXXXXX")"
cleanup() {
  rm -f -- "$TEMP_FILE"
}
trap cleanup EXIT

ssh -o BatchMode=yes "$SSH_TARGET" \
  "cd '$SOURCE_PROJECT' && docker-compose exec -T web python manage.py shell --no-imports -v 0" \
  <"$EXPORT_SCRIPT" >"$TEMP_FILE"

PYTHONDONTWRITEBYTECODE=1 python3 -c '
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
required = {
    "users", "departments", "department_links", "memberships", "reporting_lines",
    "role_grants", "tasks", "task_assignments", "task_proposals", "progress_entries",
    "task_activities", "task_history", "assignment_history", "proposal_history",
    "progress_history", "visitor_visits", "staff_availability",
    "agenda_drafts", "agenda_versions",
}
if payload.get("version") != 4 or not required.issubset(payload):
    raise SystemExit("Export CSRS distant invalide.")
' "$TEMP_FILE"

chmod 0600 "$TEMP_FILE"
mv -- "$TEMP_FILE" "$OUTPUT_FILE"
trap - EXIT
echo "Export distant CSRS v4 créé avec un mode 0600; son contenu sensible n'a pas été affiché."
