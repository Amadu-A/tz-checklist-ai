#!/usr/bin/env bash
# scripts/e2e-real.sh

set -Eeuo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

MODE="${1:-}"
PDF_FILE="${2:-}"
CHECKLIST_TAG="${3:-}"
POLL_SECONDS="${E2E_POLL_SECONDS:-5}"
TIMEOUT_SECONDS="${E2E_TIMEOUT_SECONDS:-7200}"

usage() {
  cat <<'TEXT'
Usage:
  ./scripts/e2e-real.sh tagged <pdf> <tag>
  ./scripts/e2e-real.sh auto <pdf>
  ./scripts/e2e-real.sh invalid-tag <pdf> <invalid-tag>

Supported tags:
  УУТЭ  ИТП  МКБИ  СПД  АУПТ
  UUTE  ITP  MKBI  SPD  AUPT
TEXT
}

case "${MODE}" in
  tagged|invalid-tag)
    [[ -n "${PDF_FILE}" && -n "${CHECKLIST_TAG}" ]] || {
      usage
      exit 1
    }
    ;;

  auto)
    [[ -n "${PDF_FILE}" ]] || {
      usage
      exit 1
    }
    ;;

  *)
    usage
    exit 1
    ;;
esac

[[ -f "${PDF_FILE}" ]] || {
  echo "[e2e] ERROR: file does not exist: ${PDF_FILE}"
  exit 1
}

[[ -s .env ]] || {
  echo "[e2e] ERROR: .env is missing; run ./scripts/run.sh first"
  exit 1
}

for command_name in curl python3 docker; do
  command -v "${command_name}" >/dev/null 2>&1 || {
    echo "[e2e] ERROR: ${command_name} is required"
    exit 1
  }
done

API_HOST_PORT="$(
  grep '^API_HOST_PORT=' .env \
    | tail -n 1 \
    | cut -d= -f2- \
    || true
)"

API_HOST_PORT="${API_HOST_PORT:-8110}"

BASE_URL="${TZ_CHECK_BASE_URL:-http://127.0.0.1:${API_HOST_PORT}}"
API_URL="${BASE_URL}/api/v1/tz-check"

ARTIFACT_DIR="${E2E_ARTIFACT_DIR:-${ROOT_DIR}/artifacts/e2e}"

mkdir -p "${ARTIFACT_DIR}"

TMP_DIR="$(mktemp -d)"

trap 'rm -rf "${TMP_DIR}"' EXIT

pretty_json() {
  python3 - "$1" <<'PY'
import json
import sys

with open(
    sys.argv[1],
    "r",
    encoding="utf-8",
) as stream:
    payload = json.load(
        stream
    )

print(
    json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )
)
PY
}

json_field() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

with open(
    sys.argv[1],
    "r",
    encoding="utf-8",
) as stream:
    value = json.load(
        stream
    )

for part in sys.argv[2].split(
    "."
):
    if not isinstance(
        value,
        dict,
    ):
        value = None
        break

    value = value.get(
        part
    )

    if value is None:
        break

if value is None:
    print("")

elif isinstance(
    value,
    bool,
):
    print(
        str(
            value
        ).lower()
    )

else:
    print(
        value
    )
PY
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

require_http_2xx() {
  local code="$1"
  local response_file="$2"
  local operation="$3"

  if [[ ! "${code}" =~ ^2[0-9][0-9]$ ]]; then
    echo "[e2e] ERROR: ${operation} returned HTTP ${code}"

    if [[ -s "${response_file}" ]]; then
      cat "${response_file}"
      echo
    fi

    exit 1
  fi
}

canonical_tag_data() {
  python3 - "$1" <<'PY'
import sys

mapping = {
    "уутэ": (
        "UUTE",
        "УУТЭ",
    ),
    "uute": (
        "UUTE",
        "УУТЭ",
    ),
    "итп": (
        "ITP",
        "ИТП",
    ),
    "itp": (
        "ITP",
        "ИТП",
    ),
    "мкби": (
        "MKBI",
        "МКБИ",
    ),
    "mkbi": (
        "MKBI",
        "МКБИ",
    ),
    "спд": (
        "SPD",
        "СПД",
    ),
    "spd": (
        "SPD",
        "СПД",
    ),
    "аупт": (
        "AUPT",
        "АУПТ",
    ),
    "aupt": (
        "AUPT",
        "АУПТ",
    ),
}

result = mapping.get(
    sys.argv[1]
    .strip()
    .casefold()
)

if result is None:
    raise SystemExit(
        1
    )

print(
    *result
)
PY
}

other_tag() {
  case "$1" in
    UUTE)
      echo "СПД"
      ;;

    ITP)
      echo "МКБИ"
      ;;

    MKBI)
      echo "УУТЭ"
      ;;

    SPD)
      echo "АУПТ"
      ;;

    AUPT)
      echo "ИТП"
      ;;

    *)
      echo "СПД"
      ;;
  esac
}

echo "============================================================"
echo "[e2e] mode: ${MODE}"
echo "[e2e] API: ${API_URL}"
echo "[e2e] PDF: ${PDF_FILE}"

if [[ -n "${CHECKLIST_TAG}" ]]; then
  echo "[e2e] tag: ${CHECKLIST_TAG}"
fi

echo "============================================================"

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
# INVALID TAG
# ----------------------------------------------------------------------

if [[ "${MODE}" == "invalid-tag" ]]; then
  RESPONSE="${TMP_DIR}/invalid-tag.json"

  HTTP_CODE="$(
    post_form \
      "${RESPONSE}" \
      -F "action=select" \
      -F "checklist_tag=${CHECKLIST_TAG}" \
      -F "file=@${PDF_FILE};type=application/pdf"
  )"

  if [[ "${HTTP_CODE}" != "422" ]]; then
    echo "[e2e] ERROR: invalid tag must return HTTP 422, got ${HTTP_CODE}"

    if [[ -s "${RESPONSE}" ]]; then
      cat "${RESPONSE}"
      echo
    fi

    exit 1
  fi

  pretty_json \
    "${RESPONSE}"

  echo
  echo "============================================================"
  echo "[e2e] INVALID TAG PASSED"
  echo "============================================================"

  exit 0
fi

# ----------------------------------------------------------------------
# SELECT
# ----------------------------------------------------------------------

SELECT_RESPONSE="${TMP_DIR}/select.json"

echo
echo "[e2e] action=select"

if [[ "${MODE}" == "tagged" ]]; then
  TAG_DATA="$(
    canonical_tag_data \
      "${CHECKLIST_TAG}"
  )" || {
    echo "[e2e] ERROR: unsupported test tag: ${CHECKLIST_TAG}"
    exit 1
  }

  read -r \
    EXPECTED_CHECKLIST_CODE \
    EXPECTED_CHECKLIST_TAG \
    <<< "${TAG_DATA}"

  SELECT_CODE="$(
    post_form \
      "${SELECT_RESPONSE}" \
      -F "action=select" \
      -F "checklist_tag=${CHECKLIST_TAG}" \
      -F "file=@${PDF_FILE};type=application/pdf"
  )"

else
  SELECT_CODE="$(
    post_form \
      "${SELECT_RESPONSE}" \
      -F "action=select" \
      -F "file=@${PDF_FILE};type=application/pdf"
  )"
fi

require_http_2xx \
  "${SELECT_CODE}" \
  "${SELECT_RESPONSE}" \
  "select"

pretty_json \
  "${SELECT_RESPONSE}"

REQUEST_ID="$(
  json_field \
    "${SELECT_RESPONSE}" \
    request_id
)"

JOB_STATUS="$(
  json_field \
    "${SELECT_RESPONSE}" \
    status
)"

SELECTION_MODE="$(
  json_field \
    "${SELECT_RESPONSE}" \
    selection_mode
)"

REQUIRES_CONFIRMATION="$(
  json_field \
    "${SELECT_RESPONSE}" \
    requires_confirmation
)"

if [[ -z "${REQUEST_ID}" ]]; then
  echo "[e2e] ERROR: select returned no request_id"
  exit 1
fi

echo
echo "[e2e] request_id: ${REQUEST_ID}"
echo "[e2e] selection_mode: ${SELECTION_MODE}"
echo "[e2e] status: ${JOB_STATUS}"
echo "[e2e] requires_confirmation: ${REQUIRES_CONFIRMATION}"

# ----------------------------------------------------------------------
# TAGGED FLOW
# ----------------------------------------------------------------------

if [[ "${MODE}" == "tagged" ]]; then
  CHECKLIST_CODE="$(
    json_field \
      "${SELECT_RESPONSE}" \
      checklist_code
  )"

  CHECKLIST_TAG_CANONICAL="$(
    json_field \
      "${SELECT_RESPONSE}" \
      checklist_tag
  )"

  if [[ "${SELECTION_MODE}" != "provided_tag" ]]; then
    echo "[e2e] ERROR: expected selection_mode=provided_tag"
    exit 1
  fi

  if [[ "${JOB_STATUS}" != "queued" ]]; then
    echo "[e2e] ERROR: tagged select must return queued"
    exit 1
  fi

  if [[ "${REQUIRES_CONFIRMATION}" != "false" ]]; then
    echo "[e2e] ERROR: tagged select must skip confirmation"
    exit 1
  fi

  if [[ "${CHECKLIST_CODE}" != "${EXPECTED_CHECKLIST_CODE}" ]]; then
    echo "[e2e] ERROR: checklist code mismatch"
    echo "[e2e] expected=${EXPECTED_CHECKLIST_CODE}"
    echo "[e2e] actual=${CHECKLIST_CODE}"
    exit 1
  fi

  if [[ "${CHECKLIST_TAG_CANONICAL}" != "${EXPECTED_CHECKLIST_TAG}" ]]; then
    echo "[e2e] ERROR: checklist tag mismatch"
    echo "[e2e] expected=${EXPECTED_CHECKLIST_TAG}"
    echo "[e2e] actual=${CHECKLIST_TAG_CANONICAL}"
    exit 1
  fi

  echo "[e2e] Tagged flow skipped classification/confirmation: OK"
fi

# ----------------------------------------------------------------------
# AUTO FLOW
# ----------------------------------------------------------------------

if [[ "${MODE}" == "auto" ]]; then
  RECOMMENDED_CODE="$(
    json_field \
      "${SELECT_RESPONSE}" \
      recommended_checklist
  )"

  RECOMMENDED_TAG="$(
    json_field \
      "${SELECT_RESPONSE}" \
      recommended_tag
  )"

  CONFIDENCE="$(
    json_field \
      "${SELECT_RESPONSE}" \
      confidence
  )"

  if [[ "${SELECTION_MODE}" != "automatic" ]]; then
    echo "[e2e] ERROR: expected selection_mode=automatic"
    exit 1
  fi

  if [[ "${JOB_STATUS}" != "awaiting_confirmation" ]]; then
    echo "[e2e] ERROR: auto flow must await confirmation"
    exit 1
  fi

  if [[ "${REQUIRES_CONFIRMATION}" != "true" ]]; then
    echo "[e2e] ERROR: auto flow must require confirmation"
    exit 1
  fi

  if [[ -z "${RECOMMENDED_CODE}" || -z "${RECOMMENDED_TAG}" ]]; then
    echo "[e2e] ERROR: classifier returned no recommendation"
    exit 1
  fi

  CHECKLIST_CODE="${RECOMMENDED_CODE}"
  CHECKLIST_TAG_CANONICAL="${RECOMMENDED_TAG}"

  echo "[e2e] recommended code: ${RECOMMENDED_CODE}"
  echo "[e2e] recommended tag: ${RECOMMENDED_TAG}"
  echo "[e2e] confidence: ${CONFIDENCE}"

  # Проверяем конфликт code + tag.
  WRONG_TAG="$(
    other_tag \
      "${RECOMMENDED_CODE}"
  )"

  CONFLICT_RESPONSE="${TMP_DIR}/conflict.json"

  echo
  echo "[e2e] Verify conflicting confirmation"

  CONFLICT_CODE="$(
    post_form \
      "${CONFLICT_RESPONSE}" \
      -F "action=confirm" \
      -F "request_id=${REQUEST_ID}" \
      -F "checklist_code=${RECOMMENDED_CODE}" \
      -F "checklist_tag=${WRONG_TAG}"
  )"

  if [[ "${CONFLICT_CODE}" != "400" ]]; then
    echo "[e2e] ERROR: conflicting code/tag must return HTTP 400"
    echo "[e2e] actual=${CONFLICT_CODE}"
    exit 1
  fi

  AFTER_CONFLICT="${TMP_DIR}/after-conflict.json"

  AFTER_CONFLICT_CODE="$(
    post_form \
      "${AFTER_CONFLICT}" \
      -F "action=status" \
      -F "request_id=${REQUEST_ID}"
  )"

  require_http_2xx \
    "${AFTER_CONFLICT_CODE}" \
    "${AFTER_CONFLICT}" \
    "status after conflicting confirm"

  AFTER_CONFLICT_STATUS="$(
    json_field \
      "${AFTER_CONFLICT}" \
      status
  )"

  if [[ "${AFTER_CONFLICT_STATUS}" != "awaiting_confirmation" ]]; then
    echo "[e2e] ERROR: rejected confirmation mutated job state"
    exit 1
  fi

  echo "[e2e] Conflicting confirmation rejected without state mutation: OK"

  # Правильное подтверждение русским тегом.
  CONFIRM_RESPONSE="${TMP_DIR}/confirm.json"

  echo
  echo "[e2e] Confirm recommendation by public tag=${RECOMMENDED_TAG}"

  CONFIRM_CODE="$(
    post_form \
      "${CONFIRM_RESPONSE}" \
      -F "action=confirm" \
      -F "request_id=${REQUEST_ID}" \
      -F "checklist_tag=${RECOMMENDED_TAG}"
  )"

  require_http_2xx \
    "${CONFIRM_CODE}" \
    "${CONFIRM_RESPONSE}" \
    "confirm by public tag"

  pretty_json \
    "${CONFIRM_RESPONSE}"

  CONFIRMED_CODE="$(
    json_field \
      "${CONFIRM_RESPONSE}" \
      checklist_code
  )"

  CONFIRMED_TAG="$(
    json_field \
      "${CONFIRM_RESPONSE}" \
      checklist_tag
  )"

  if [[ "${CONFIRMED_CODE}" != "${RECOMMENDED_CODE}" ]]; then
    echo "[e2e] ERROR: confirmed code mismatch"
    exit 1
  fi

  if [[ "${CONFIRMED_TAG}" != "${RECOMMENDED_TAG}" ]]; then
    echo "[e2e] ERROR: confirmed tag mismatch"
    exit 1
  fi

  # Повторное подтверждение не должно ставить второй logical job.
  REPEAT_RESPONSE="${TMP_DIR}/repeat-confirm.json"

  echo
  echo "[e2e] Repeat confirmation by internal code"

  REPEAT_CODE="$(
    post_form \
      "${REPEAT_RESPONSE}" \
      -F "action=confirm" \
      -F "request_id=${REQUEST_ID}" \
      -F "checklist_code=${RECOMMENDED_CODE}"
  )"

  require_http_2xx \
    "${REPEAT_CODE}" \
    "${REPEAT_RESPONSE}" \
    "repeated confirm"

  REPEAT_STATUS="$(
    json_field \
      "${REPEAT_RESPONSE}" \
      status
  )"

  case "${REPEAT_STATUS}" in
    queued|processing|completed)
      echo "[e2e] Repeated confirmation is idempotent: OK"
      ;;

    *)
      echo "[e2e] ERROR: unexpected repeated-confirm status=${REPEAT_STATUS}"
      exit 1
      ;;
  esac
fi

# ----------------------------------------------------------------------
# STATUS POLLING
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

  require_http_2xx \
    "${STATUS_CODE}" \
    "${STATUS_RESPONSE}" \
    "status"

  JOB_STATUS="$(
    json_field \
      "${STATUS_RESPONSE}" \
      status
  )"

  PROGRESS="$(
    json_field \
      "${STATUS_RESPONSE}" \
      progress_percent
  )"

  STATUS_TAG="$(
    json_field \
      "${STATUS_RESPONSE}" \
      checklist_tag
  )"

  echo "[e2e] status=${JOB_STATUS} progress=${PROGRESS}% tag=${STATUS_TAG}"

  case "${JOB_STATUS}" in
    completed)
      break
      ;;

    failed)
      echo "[e2e] ERROR: worker returned failed"

      pretty_json \
        "${STATUS_RESPONSE}"

      docker compose logs \
        --tail=200 \
        worker

      exit 1
      ;;

    queued|processing)
      ;;

    *)
      echo "[e2e] ERROR: unexpected job status=${JOB_STATUS}"
      exit 1
      ;;
  esac

  CURRENT_TIMESTAMP="$(
    date +%s
  )"

  ELAPSED=$((CURRENT_TIMESTAMP - START_TIMESTAMP))

  if (( ELAPSED > TIMEOUT_SECONDS )); then
    echo "[e2e] ERROR: timeout after ${TIMEOUT_SECONDS}s"

    docker compose logs \
      --tail=200 \
      worker

    exit 1
  fi

  sleep \
    "${POLL_SECONDS}"
done

# ----------------------------------------------------------------------
# BACKEND STATE BEFORE RESULT DELIVERY
# ----------------------------------------------------------------------

echo
echo "[e2e] Verify temporary backend state before delivery"

if docker compose exec -T api \
  sh -lc \
  "test ! -e '/data/jobs/${REQUEST_ID}/input.pdf' && \
   test ! -e '/data/jobs/${REQUEST_ID}/source_filename.txt' && \
   test -f '/data/jobs/${REQUEST_ID}/result.json'"
then
  echo "[e2e] input.pdf deleted: OK"
  echo "[e2e] source_filename.txt deleted: OK"
  echo "[e2e] temporary result.json exists: OK"
else
  echo "[e2e] ERROR: unexpected completed-job filesystem state"

  docker compose exec -T api \
    sh -lc \
    "find '/data/jobs/${REQUEST_ID}' -maxdepth 2 -ls 2>/dev/null || true"

  exit 1
fi

# ----------------------------------------------------------------------
# RESULT
# ----------------------------------------------------------------------

PDF_BASENAME="$(
  basename \
    "${PDF_FILE}"
)"

PDF_STEM="${PDF_BASENAME%.*}"

RESULT_FILE="${ARTIFACT_DIR}/${PDF_STEM}-${REQUEST_ID}.json"
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

  if [[ -s "${RESULT_FILE}" ]]; then
    cat "${RESULT_FILE}"
    echo
  fi

  rm -f \
    "${RESULT_FILE}"

  exit 1
fi

if ! grep \
  -qi \
  '^content-type: application/json' \
  "${RESULT_HEADERS}"
then
  echo "[e2e] ERROR: result content-type is not application/json"

  cat \
    "${RESULT_HEADERS}"

  exit 1
fi

# ----------------------------------------------------------------------
# JSON CONTRACT
# ----------------------------------------------------------------------

echo
echo "[e2e] Validate JSON result contract"

python3 - \
  "${RESULT_FILE}" \
  "${REQUEST_ID}" \
  "${CHECKLIST_CODE}" \
  "${CHECKLIST_TAG_CANONICAL}" \
  "${PDF_BASENAME}" <<'PY'
import json
import sys
from datetime import datetime

(
    path,
    request_id,
    checklist_code,
    checklist_tag,
    filename,
) = sys.argv[1:]

with open(
    path,
    "r",
    encoding="utf-8",
) as stream:
    payload = json.load(
        stream
    )

metadata = payload.get(
    "metadata"
)

questions = payload.get(
    "questions"
)

if not isinstance(
    metadata,
    dict,
):
    raise SystemExit(
        "metadata must be an object"
    )

if not isinstance(
    questions,
    list,
):
    raise SystemExit(
        "questions must be an array"
    )

required_metadata = {
    "request_id",
    "checklist_type",
    "checklist_tag",
    "checklist_code",
    "source_filename",
    "processing_seconds",
    "search_seconds",
    "completed_at",
    "question_count",
}

missing = (
    required_metadata
    - set(
        metadata
    )
)

if missing:
    raise SystemExit(
        "missing metadata fields: "
        + ", ".join(
            sorted(
                missing
            )
        )
    )

if (
    metadata["request_id"]
    != request_id
):
    raise SystemExit(
        "request_id mismatch"
    )

if (
    metadata["checklist_code"]
    != checklist_code
):
    raise SystemExit(
        "checklist_code mismatch"
    )

if (
    metadata["checklist_tag"]
    != checklist_tag
):
    raise SystemExit(
        "checklist_tag mismatch"
    )

if (
    metadata["source_filename"]
    != filename
):
    raise SystemExit(
        "source_filename mismatch"
    )

if (
    not isinstance(
        metadata["checklist_type"],
        str,
    )
    or not metadata[
        "checklist_type"
    ].strip()
):
    raise SystemExit(
        "checklist_type must be non-empty"
    )

for field in (
    "processing_seconds",
    "search_seconds",
):
    value = metadata[
        field
    ]

    if (
        not isinstance(
            value,
            (
                int,
                float,
            ),
        )
        or value < 0
    ):
        raise SystemExit(
            f"{field} must be non-negative numeric"
        )

if (
    metadata["search_seconds"]
    > metadata["processing_seconds"]
    + 0.01
):
    raise SystemExit(
        "search_seconds cannot exceed processing_seconds"
    )

datetime.fromisoformat(
    str(
        metadata[
            "completed_at"
        ]
    ).replace(
        "Z",
        "+00:00",
    )
)

question_count = metadata[
    "question_count"
]

if (
    not isinstance(
        question_count,
        int,
    )
    or question_count <= 0
):
    raise SystemExit(
        "question_count must be a positive integer"
    )

if (
    len(
        questions
    )
    != question_count
):
    raise SystemExit(
        "question_count mismatch"
    )

filled = 0

for index, item in enumerate(
    questions,
    start=1,
):
    if not isinstance(
        item,
        dict,
    ):
        raise SystemExit(
            f"question #{index} must be an object"
        )

    number = item.get(
        "number"
    )

    question = item.get(
        "question"
    )

    answer = item.get(
        "answer"
    )

    if (
        not isinstance(
            number,
            str,
        )
        or not number.strip()
    ):
        raise SystemExit(
            f"question #{index}: invalid number"
        )

    if (
        not isinstance(
            question,
            str,
        )
        or not question.strip()
    ):
        raise SystemExit(
            f"question #{index}: invalid question"
        )

    if not isinstance(
        answer,
        str,
    ):
        raise SystemExit(
            f"question #{index}: answer must be a string"
        )

    if answer.strip():
        filled += 1

print(
    "[e2e] JSON schema: OK"
)

print(
    "[e2e] checklist:",
    metadata["checklist_tag"],
    f"({metadata['checklist_code']})",
)

print(
    "[e2e] source filename:",
    metadata["source_filename"],
)

print(
    "[e2e] processing_seconds:",
    metadata["processing_seconds"],
)

print(
    "[e2e] search_seconds:",
    metadata["search_seconds"],
)

print(
    "[e2e] questions:",
    question_count,
)

print(
    "[e2e] filled answers:",
    filled,
)

print(
    "[e2e] blank answers:",
    question_count - filled,
)

print(
    "[e2e] first non-empty answers:"
)

shown = 0

for item in questions:
    if not item[
        "answer"
    ].strip():
        continue

    print(
        f"  {item['number']}. "
        f"{item['question']}"
    )

    print(
        "     ->",
        item["answer"],
    )

    shown += 1

    if shown >= 12:
        break

if shown == 0:
    print(
        "  <no filled answers>"
    )
PY

echo
echo "[e2e] Client-side JSON:"
echo "${RESULT_FILE}"

du -h \
  "${RESULT_FILE}"

# ----------------------------------------------------------------------
# ONE-TIME RESULT
# ----------------------------------------------------------------------

SECOND_RESPONSE="${TMP_DIR}/second-result.json"

SECOND_CODE="$(
  post_form \
    "${SECOND_RESPONSE}" \
    -F "action=result" \
    -F "request_id=${REQUEST_ID}"
)"

if [[ "${SECOND_CODE}" != "404" ]]; then
  echo "[e2e] ERROR: second result call must return 404"
  echo "[e2e] actual=${SECOND_CODE}"
  exit 1
fi

echo "[e2e] One-time result delivery: OK"

# ----------------------------------------------------------------------
# BACKEND CLEANUP
# ----------------------------------------------------------------------

if docker compose exec -T api \
  sh -lc \
  "test ! -e '/data/jobs/${REQUEST_ID}'"
then
  echo "[e2e] Backend job directory removed: OK"
else
  echo "[e2e] ERROR: backend job directory still exists"
  exit 1
fi

if docker compose exec -T api \
  python - \
  "${REQUEST_ID}" <<'PY'
import sys
from uuid import UUID

from app.core.container import get_container

state = (
    get_container()
    .job_repository
    .get(
        UUID(
            sys.argv[1]
        )
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
  echo "[e2e] SQLite metadata removed: OK"
else
  echo "[e2e] ERROR: SQLite metadata still exists"
  exit 1
fi

echo
echo "============================================================"
echo "[e2e] REAL JSON E2E PASSED"
echo "[e2e] mode: ${MODE}"
echo "[e2e] request_id: ${REQUEST_ID}"
echo "[e2e] checklist: ${CHECKLIST_TAG_CANONICAL} (${CHECKLIST_CODE})"
echo "[e2e] client result: ${RESULT_FILE}"
echo "[e2e] backend input/result/metadata: deleted"
echo "============================================================"