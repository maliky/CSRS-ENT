#!/usr/bin/env bash
set -Eeuo pipefail

readonly SOURCE_PROJECT="${1:-/home/jil/csrs_report}"
readonly OUTPUT_FILE="${2:-}"
readonly REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly EXPORT_SCRIPT="${REPOSITORY_ROOT}/scripts/export_csrs_source.py"
readonly SOURCE_CONTAINER="${CSRS_SOURCE_CONTAINER:-}"

if [[ -z $OUTPUT_FILE ]]; then
  echo "Usage: $0 [DEPOT_CSRS_REPORT] FICHIER_JSON" >&2
  exit 2
fi
if [[ ! -f ${SOURCE_PROJECT}/manage.py ]]; then
  echo "Projet source introuvable." >&2
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

if [[ -n $SOURCE_CONTAINER ]]; then
  docker exec -i "$SOURCE_CONTAINER" \
    python manage.py shell --no-imports -v 0 <"$EXPORT_SCRIPT" >"$TEMP_FILE"
else
  (
    cd "$SOURCE_PROJECT"
    PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=csrs \
      python manage.py shell --no-imports -v 0 <"$EXPORT_SCRIPT" >"$TEMP_FILE"
  )
fi

PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=csrs python -c '
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
    raise SystemExit("Export CSRS invalide.")
' "$TEMP_FILE"

chmod 0600 "$TEMP_FILE"
mv -- "$TEMP_FILE" "$OUTPUT_FILE"
trap - EXIT
echo "Export CSRS v3 créé avec un mode 0600; son contenu sensible n'a pas été affiché."
