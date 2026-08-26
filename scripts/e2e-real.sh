#!/usr/bin/env bash
# scripts/e2e-real.sh

set -Eeuo pipefail

# Клиентские копии реальных документов/отчётов доступны
# только владельцу файлов.
umask 077

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  pwd
)"

cd "${ROOT_DIR}"

PDF_FILE="${1:-}"
CHECKLIST_OVERRIDE="${2:-}"

if [[ -z "${PDF_FILE}" ]]; then
  echo "[e2e] ERROR: PDF path is required"
  echo
  echo "Available private PDF fixtures:"

  find tests/fixtures/private \
    -maxdepth 1 \
    -type f \
    -iname '*.pdf' \
    -print \
    2>/dev/null || true

  echo
  echo "Usage:"
  echo "./scripts/e2e-real.sh tests/fixtures/private/file.pdf"
  echo "./scripts/e2e-real.sh tests/fixtures/private/file.pdf UUTE"

  exit 1
fi

if [[ ! -f "${PDF_FILE}" ]]; then
  echo "[e2e] ERROR: file does not exist:"
  echo "${PDF_FILE}"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[e2e] ERROR: curl is required"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[e2e] ERROR: python3 is required"
  exit 1
fi

if [[ ! -s .env ]]; then
  echo "[e2e] ERROR: .env is missing"
  echo "[e2e] Run ./scripts/run.sh first"
  exit 1
fi

API_HOST_PORT="$(
  grep '^API_HOST_PORT=' .env \
    | tail -n 1 \
    | cut -d= -f2- \
    || true
)"

API_HOST_PORT="${API_HOST_PORT:-8110}"

BASE_URL="${TZ_CHECK_BASE_URL:-http://127.0.0.1:${API_HOST_PORT}}"

API_URL="${BASE_URL}/api/v1/tz-check"

POLL_SECONDS="${E2E_POLL_SECONDS:-5}"

TIMEOUT_SECONDS="${E2E_TIMEOUT_SECONDS:-7200}"

ARTIFACT_DIR="${E2E_ARTIFACT_DIR:-${ROOT_DIR}/artifacts/e2e}"

mkdir -p "${ARTIFACT_DIR}"

TMP_DIR="$(
  mktemp -d
)"

cleanup() {
  rm -rf "${TMP_DIR}"
}

trap cleanup EXIT

json_field() {
  local json_file="$1"
  local field_name="$2"

  python3 - "${json_file}" "${field_name}" <<'PY'
import json
import sys

json_path = sys.argv[1]
field_name = sys.argv[2]

with open(
    json_path,
    "r",
    encoding="utf-8",
) as stream:
    payload = json.load(stream)

value = payload.get(
    field_name
)

if value is None:
    print("")
elif isinstance(
    value,
    bool,
):
    print(
        str(value).lower()
    )
else:
    print(
        value
    )
PY
}

pretty_json() {
  local json_file="$1"

  python3 -m json.tool \
    "${json_file}"
}

post_form() {
  local output_file="$1"

  shift

  curl \
    -sS \
    -o "${output_file}" \
    -w '%{http_code}' \
    "$@" \
    "${API_URL}"
}

require_success() {
  local http_code="$1"
  local response_file="$2"
  local operation="$3"

  if [[ ! "${http_code}" =~ ^2[0-9][0-9]$ ]]; then
    echo "[e2e] ERROR: ${operation} returned HTTP ${http_code}"

    if [[ -s "${response_file}" ]]; then
      cat "${response_file}"
      echo
    fi

    exit 1
  fi
}

echo "[e2e] API: ${API_URL}"
echo "[e2e] PDF: ${PDF_FILE}"

echo "[e2e] Check liveness"

curl \
  -fsS \
  "${BASE_URL}/health/live" \
  >/dev/null

echo "[e2e] Check readiness"

curl \
  -fsS \
  "${BASE_URL}/health/ready" \
  >/dev/null

echo "[e2e] Service is ready"

# ----------------------------------------------------------------------
# SELECT
# ----------------------------------------------------------------------

SELECT_RESPONSE="${TMP_DIR}/select.json"

echo
echo "[e2e] action=select"

SELECT_CODE="$(
  post_form \
    "${SELECT_RESPONSE}" \
    -F "action=select" \
    -F "file=@${PDF_FILE};type=application/pdf"
)"

require_success \
  "${SELECT_CODE}" \
  "${SELECT_RESPONSE}" \
  "select"

pretty_json \
  "${SELECT_RESPONSE}"

REQUEST_ID="$(
  json_field \
    "${SELECT_RESPONSE}" \
    "request_id"
)"

RECOMMENDED_CHECKLIST="$(
  json_field \
    "${SELECT_RESPONSE}" \
    "recommended_checklist"
)"

CONFIDENCE="$(
  json_field \
    "${SELECT_RESPONSE}" \
    "confidence"
)"

if [[ -z "${REQUEST_ID}" ]]; then
  echo "[e2e] ERROR: select response contains no request_id"
  exit 1
fi

echo
echo "[e2e] request_id: ${REQUEST_ID}"
echo "[e2e] recommended checklist: ${RECOMMENDED_CHECKLIST:-<none>}"
echo "[e2e] confidence: ${CONFIDENCE:-<none>}"

if [[ -n "${CHECKLIST_OVERRIDE}" ]]; then
  CHECKLIST_CODE="${CHECKLIST_OVERRIDE^^}"

  echo "[e2e] Using checklist override: ${CHECKLIST_CODE}"
else
  CHECKLIST_CODE="${RECOMMENDED_CHECKLIST}"

  echo "[e2e] Confirming recommendation: ${CHECKLIST_CODE}"
fi

case "${CHECKLIST_CODE}" in
  UUTE|ITP|MKBI|SPD|AUPT)
    ;;
  *)
    echo "[e2e] ERROR: invalid or missing checklist code:"
    echo "${CHECKLIST_CODE}"
    exit 1
    ;;
esac

# ----------------------------------------------------------------------
# CONFIRM
# ----------------------------------------------------------------------

CONFIRM_RESPONSE="${TMP_DIR}/confirm.json"

echo
echo "[e2e] action=confirm"

CONFIRM_CODE="$(
  post_form \
    "${CONFIRM_RESPONSE}" \
    -F "action=confirm" \
    -F "request_id=${REQUEST_ID}" \
    -F "checklist_code=${CHECKLIST_CODE}"
)"

require_success \
  "${CONFIRM_CODE}" \
  "${CONFIRM_RESPONSE}" \
  "confirm"

pretty_json \
  "${CONFIRM_RESPONSE}"

# ----------------------------------------------------------------------
# STATUS
# ----------------------------------------------------------------------

echo
echo "[e2e] Waiting for worker"

START_TIMESTAMP="$(
  date +%s
)"

while true; do
  STATUS_RESPONSE="${TMP_DIR}/status.json"

  STATUS_CODE="$(
    post_form \
      "${STATUS_RESPONSE}" \
      -F "action=status" \
      -F "request_id=${REQUEST_ID}"
  )"

  require_success \
    "${STATUS_CODE}" \
    "${STATUS_RESPONSE}" \
    "status"

  JOB_STATUS="$(
    json_field \
      "${STATUS_RESPONSE}" \
      "status"
  )"

  PROGRESS="$(
    json_field \
      "${STATUS_RESPONSE}" \
      "progress_percent"
  )"

  echo "[e2e] status=${JOB_STATUS} progress=${PROGRESS}%"

  case "${JOB_STATUS}" in
    completed)
      break
      ;;

    failed)
      echo
      echo "[e2e] ERROR: worker returned FAILED"

      pretty_json \
        "${STATUS_RESPONSE}"

      echo
      echo "[e2e] Worker logs:"

      docker compose logs \
        --tail=200 \
        worker

      exit 1
      ;;

    awaiting_confirmation|queued|processing)
      ;;

    *)
      echo "[e2e] ERROR: unexpected job status: ${JOB_STATUS}"
      exit 1
      ;;
  esac

  CURRENT_TIMESTAMP="$(
    date +%s
  )"

  ELAPSED="$(
    (
      CURRENT_TIMESTAMP
      - START_TIMESTAMP
    )
  )"

  if (( ELAPSED > TIMEOUT_SECONDS )); then
    echo "[e2e] ERROR: timeout after ${TIMEOUT_SECONDS}s"

    docker compose logs \
      --tail=200 \
      worker

    exit 1
  fi

  sleep "${POLL_SECONDS}"
done

# ----------------------------------------------------------------------
# RESULT
# ----------------------------------------------------------------------

PDF_BASENAME="$(
  basename \
    "${PDF_FILE}"
)"

PDF_STEM="${PDF_BASENAME%.*}"

RESULT_FILE="${ARTIFACT_DIR}/${PDF_STEM}-${REQUEST_ID}.pdf"

RESULT_HEADERS="${TMP_DIR}/result.headers"

echo
echo "[e2e] action=result"

RESULT_CODE="$(
  curl \
    -sS \
    -D "${RESULT_HEADERS}" \
    -o "${RESULT_FILE}" \
    -w '%{http_code}' \
    -F "action=result" \
    -F "request_id=${REQUEST_ID}" \
    "${API_URL}"
)"

if [[ "${RESULT_CODE}" != "200" ]]; then
  echo "[e2e] ERROR: result returned HTTP ${RESULT_CODE}"

  cat "${RESULT_FILE}" \
    2>/dev/null \
    || true

  rm -f \
    "${RESULT_FILE}"

  exit 1
fi

if ! grep \
  -qi \
  '^content-type: application/pdf' \
  "${RESULT_HEADERS}"
then
  echo "[e2e] ERROR: response content-type is not application/pdf"
  cat "${RESULT_HEADERS}"
  exit 1
fi

if [[ "$(
  head -c 5 \
    "${RESULT_FILE}"
)" != "%PDF-" ]]; then
  echo "[e2e] ERROR: downloaded result has no PDF signature"
  exit 1
fi

echo "[e2e] Result downloaded:"
echo "${RESULT_FILE}"

echo "[e2e] Result size:"
du -h \
  "${RESULT_FILE}"

# ----------------------------------------------------------------------
# ONE-TIME DELIVERY
# ----------------------------------------------------------------------

SECOND_RESULT_RESPONSE="${TMP_DIR}/second-result.json"

echo
echo "[e2e] Verify one-time result delivery"

SECOND_RESULT_CODE="$(
  post_form \
    "${SECOND_RESULT_RESPONSE}" \
    -F "action=result" \
    -F "request_id=${REQUEST_ID}"
)"

if [[ "${SECOND_RESULT_CODE}" != "404" ]]; then
  echo "[e2e] ERROR: second result call must return 404"
  echo "[e2e] Actual HTTP: ${SECOND_RESULT_CODE}"

  if [[ -s "${SECOND_RESULT_RESPONSE}" ]]; then
    cat "${SECOND_RESULT_RESPONSE}"
    echo
  fi

  exit 1
fi

echo "[e2e] Second result call returned 404: OK"

# ----------------------------------------------------------------------
# BACKEND FILESYSTEM
# ----------------------------------------------------------------------

echo
echo "[e2e] Verify backend job directory was removed"

if docker compose exec -T api \
  sh -lc \
  "test ! -e '/data/jobs/${REQUEST_ID}'"
then
  echo "[e2e] /data/jobs/${REQUEST_ID} does not exist: OK"
else
  echo "[e2e] ERROR: backend job directory still exists"

  docker compose exec -T api \
    sh -lc \
    "find '/data/jobs/${REQUEST_ID}' -maxdepth 2 -ls"

  exit 1
fi

# ----------------------------------------------------------------------
# BACKEND METADATA
# ----------------------------------------------------------------------

echo
echo "[e2e] Verify SQLite metadata was removed"

if docker compose exec -T api \
  python - \
  "${REQUEST_ID}" <<'PY'
import sys
from uuid import UUID

from app.core.container import get_container

request_id = UUID(
    sys.argv[1]
)

state = (
    get_container()
    .job_repository
    .get(
        request_id
    )
)

if state is not None:
    print(
        state
    )
    raise SystemExit(
        1
    )
PY
then
  echo "[e2e] SQLite metadata does not exist: OK"
else
  echo "[e2e] ERROR: SQLite metadata still exists"
  exit 1
fi

# ----------------------------------------------------------------------
# CLIENT-SIDE REPORT PREVIEW
# ----------------------------------------------------------------------

echo
echo "[e2e] PDF text preview"

RESULT_DIRECTORY="$(
  cd "$(
    dirname \
      "${RESULT_FILE}"
  )"
  pwd
)"

RESULT_NAME="$(
  basename \
    "${RESULT_FILE}"
)"

docker compose run \
  --rm \
  -T \
  --no-deps \
  -v "${RESULT_DIRECTORY}:/inspect:ro" \
  api \
  python - \
  "${RESULT_NAME}" <<'PY'
import sys

import pymupdf

path = (
    "/inspect/"
    + sys.argv[1]
)

document = pymupdf.open(
    path
)

text = "\n".join(
    page.get_text()
    for page in document
)

print(
    f"[e2e] pages={document.page_count}"
)

print(
    "[e2e] first 5000 extracted characters:"
)

print(
    text[:5000]
    if text.strip()
    else "<PDF contains no extractable text>"
)
PY

echo
echo "============================================================"
echo "[e2e] REAL E2E PASSED"
echo "[e2e] request_id: ${REQUEST_ID}"
echo "[e2e] checklist: ${CHECKLIST_CODE}"
echo "[e2e] report: ${RESULT_FILE}"
echo "[e2e] backend input/result/metadata: deleted"
echo "============================================================"