#!/usr/bin/env bash
# scripts/e2e-real.sh

set -Eeuo pipefail

# Реальные ТЗ и полученные JSON содержат пользовательские данные.
umask 077

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  pwd
)"

cd "${ROOT_DIR}"

MODE="${1:-}"
PDF_FILE="${2:-}"
CHECKLIST_TAG="${3:-}"

POLL_SECONDS="${E2E_POLL_SECONDS:-5}"
TIMEOUT_SECONDS="${E2E_TIMEOUT_SECONDS:-7200}"

if [[ ! -s .env ]]; then
  echo "[e2e] ERROR: .env is missing"
  echo "[e2e] Run ./scripts/run.sh first"
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

usage() {
  echo "Usage:"
  echo
  echo "  Auto-detection + confirmation:"
  echo "  ./scripts/e2e-real.sh auto <pdf>"
  echo
  echo "  Explicit checklist tag:"
  echo "  ./scripts/e2e-real.sh tagged <pdf> <tag>"
  echo
  echo "  Invalid-tag validation:"
  echo "  ./scripts/e2e-real.sh invalid-tag <pdf> <invalid-tag>"
  echo
  echo "Supported tags:"
  echo "  УУТЭ  ИТП  МКБИ  СПД  АУПТ"
  echo
  echo "Latin aliases are also accepted:"
  echo "  UUTE  ITP  MKBI  SPD  AUPT"
}

case "${MODE}" in
  auto)
    if [[ -z "${PDF_FILE}" ]]; then
      usage
      exit 1
    fi
    ;;

  tagged)
    if [[ -z "${PDF_FILE}" || -z "${CHECKLIST_TAG}" ]]; then
      usage
      exit 1
    fi
    ;;

  invalid-tag)
    if [[ -z "${PDF_FILE}" || -z "${CHECKLIST_TAG}" ]]; then
      usage
      exit 1
    fi
    ;;

  *)
    usage
    exit 1
    ;;
esac

if [[ ! -f "${PDF_FILE}" ]]; then
  echo "[e2e] ERROR: file does not exist:"
  echo "${PDF_FILE}"
  exit 1
fi

API_HOST_PORT="$(
  grep '^API_HOST_PORT=' .env \
    | tail -n 1 \
    | cut -d= -f2- \
    || true
)"

API_HOST_PORT="${API_HOST_PORT:-8110}"

BASE_URL="${
  TZ_CHECK_BASE_URL:-
  http://127.0.0.1:${API_HOST_PORT}
}"

# Удаляем возможные whitespace/newline из multiline expansion.
BASE_URL="$(
  printf '%s' "${BASE_URL}" \
    | tr -d '\r\n '
)"

API_URL="${BASE_URL}/api/v1/tz-check"

ARTIFACT_DIR="${
  E2E_ARTIFACT_DIR:-
  ${ROOT_DIR}/artifacts/e2e
}"

ARTIFACT_DIR="$(
  printf '%s' "${ARTIFACT_DIR}" \
    | tr -d '\r\n'
)"

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
  local field_path="$2"

  python3 - \
    "${json_file}" \
    "${field_path}" <<'PY'
import json
import sys

path = sys.argv[1]
field_path = sys.argv[2]

with open(
    path,
    "r",
    encoding="utf-8",
) as stream:
    value = json.load(stream)

for part in field_path.split("."):
    if not isinstance(value, dict):
        value = None
        break

    value = value.get(
        part
    )

    if value is None:
        break

if value is None:
    print("")
elif isinstance(value, bool):
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
    --no-ensure-ascii \
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
    echo
    echo "[e2e] ERROR: ${operation} returned HTTP ${http_code}"

    if [[ -s "${response_file}" ]]; then
      cat "${response_file}"
      echo
    fi

    exit 1
  fi
}

canonical_tag_data() {
  local supplied_tag="$1"

  python3 - \
    "${supplied_tag}" <<'PY'
import sys

value = (
    sys.argv[1]
    .strip()
    .casefold()
)

mapping = {
    "уутэ": ("UUTE", "УУТЭ"),
    "uute": ("UUTE", "УУТЭ"),

    "итп": ("ITP", "ИТП"),
    "itp": ("ITP", "ИТП"),

    "мкби": ("MKBI", "МКБИ"),
    "mkbi": ("MKBI", "МКБИ"),

    "спд": ("SPD", "СПД"),
    "spd": ("SPD", "СПД"),

    "аупт": ("AUPT", "АУПТ"),
    "aupt": ("AUPT", "АУПТ"),
}

result = mapping.get(
    value
)

if result is None:
    raise SystemExit(
        1
    )

print(
    result[0],
    result[1],
)
PY
}

other_tag() {
  local checklist_code="$1"

  case "${checklist_code}" in
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

echo
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

# ======================================================================
# INVALID TAG
# ======================================================================

if [[ "${MODE}" == "invalid-tag" ]]; then
  RESPONSE="${TMP_DIR}/invalid-tag.json"

  echo
  echo "[e2e] Send deliberately invalid checklist_tag"

  HTTP_CODE="$(
    post_form \
      "${RESPONSE}" \
      -F "action=select" \
      -F "checklist_tag=${CHECKLIST_TAG}" \
      -F "file=@${PDF_FILE};type=application/pdf"
  )"

  echo "[e2e] HTTP ${HTTP_CODE}"

  if [[ "${HTTP_CODE}" != "422" ]]; then
    echo "[e2e] ERROR: invalid tag must return HTTP 422"

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
  echo "[e2e] HTTP 422 received as expected"
  echo "============================================================"

  exit 0
fi

# ======================================================================
# SELECT
# ======================================================================

SELECT_RESPONSE="${TMP_DIR}/select.json"

echo
echo "[e2e] action=select"

if [[ "${MODE}" == "tagged" ]]; then
  if ! TAG_DATA="$(
    canonical_tag_data \
      "${CHECKLIST_TAG}"
  )"; then
    echo "[e2e] ERROR: unsupported test tag: ${CHECKLIST_TAG}"
    exit 1
  fi

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

JOB_STATUS="$(
  json_field \
    "${SELECT_RESPONSE}" \
    "status"
)"

SELECTION_MODE="$(
  json_field \
    "${SELECT_RESPONSE}" \
    "selection_mode"
)"

REQUIRES_CONFIRMATION="$(
  json_field \
    "${SELECT_RESPONSE}" \
    "requires_confirmation"
)"

if [[ -z "${REQUEST_ID}" ]]; then
  echo "[e2e] ERROR: select response contains no request_id"
  exit 1
fi

echo
echo "[e2e] request_id: ${REQUEST_ID}"
echo "[e2e] selection_mode: ${SELECTION_MODE}"
echo "[e2e] status: ${JOB_STATUS}"
echo "[e2e] requires_confirmation: ${REQUIRES_CONFIRMATION}"

# ======================================================================
# TAGGED FLOW
# ======================================================================

if [[ "${MODE}" == "tagged" ]]; then
  ACTUAL_CODE="$(
    json_field \
      "${SELECT_RESPONSE}" \
      "checklist_code"
  )"

  ACTUAL_TAG="$(
    json_field \
      "${SELECT_RESPONSE}" \
      "checklist_tag"
  )"

  if [[ "${SELECTION_MODE}" != "provided_tag" ]]; then
    echo "[e2e] ERROR: tagged request did not use provided_tag"
    exit 1
  fi

  if [[ "${JOB_STATUS}" != "queued" ]]; then
    echo "[e2e] ERROR: tagged request must immediately be QUEUED"
    exit 1
  fi

  if [[ "${REQUIRES_CONFIRMATION}" != "false" ]]; then
    echo "[e2e] ERROR: tagged request must not require confirmation"
    exit 1
  fi

  if [[ "${ACTUAL_CODE}" != "${EXPECTED_CHECKLIST_CODE}" ]]; then
    echo "[e2e] ERROR: checklist code mismatch"
    echo "[e2e] expected: ${EXPECTED_CHECKLIST_CODE}"
    echo "[e2e] actual:   ${ACTUAL_CODE}"
    exit 1
  fi

  if [[ "${ACTUAL_TAG}" != "${EXPECTED_CHECKLIST_TAG}" ]]; then
    echo "[e2e] ERROR: canonical checklist tag mismatch"
    echo "[e2e] expected: ${EXPECTED_CHECKLIST_TAG}"
    echo "[e2e] actual:   ${ACTUAL_TAG}"
    exit 1
  fi

  CHECKLIST_CODE="${ACTUAL_CODE}"
  CHECKLIST_TAG_CANONICAL="${ACTUAL_TAG}"

  echo
  echo "[e2e] Tagged flow skipped classification confirmation: OK"
fi

# ======================================================================
# AUTO FLOW + CONFIRMATION TESTS
# ======================================================================

if [[ "${MODE}" == "auto" ]]; then
  RECOMMENDED_CODE="$(
    json_field \
      "${SELECT_RESPONSE}" \
      "recommended_checklist"
  )"

  RECOMMENDED_TAG="$(
    json_field \
      "${SELECT_RESPONSE}" \
      "recommended_tag"
  )"

  CONFIDENCE="$(
    json_field \
      "${SELECT_RESPONSE}" \
      "confidence"
  )"

  echo
  echo "[e2e] recommended code: ${RECOMMENDED_CODE:-<none>}"
  echo "[e2e] recommended tag: ${RECOMMENDED_TAG:-<none>}"
  echo "[e2e] confidence: ${CONFIDENCE:-<none>}"

  if [[ "${SELECTION_MODE}" != "automatic" ]]; then
    echo "[e2e] ERROR: request without tag must use automatic selection"
    exit 1
  fi

  if [[ "${JOB_STATUS}" != "awaiting_confirmation" ]]; then
    echo "[e2e] ERROR: automatic flow must await confirmation"
    exit 1
  fi

  if [[ "${REQUIRES_CONFIRMATION}" != "true" ]]; then
    echo "[e2e] ERROR: automatic flow must require confirmation"
    exit 1
  fi

  if [[ -z "${RECOMMENDED_CODE}" || -z "${RECOMMENDED_TAG}" ]]; then
    echo "[e2e] ERROR: auto classifier returned no recommendation"
    exit 1
  fi

  CHECKLIST_CODE="${RECOMMENDED_CODE}"
  CHECKLIST_TAG_CANONICAL="${RECOMMENDED_TAG}"

  # --------------------------------------------------------------------
  # CONFLICTING CONFIRM
  # --------------------------------------------------------------------

  WRONG_TAG="$(
    other_tag \
      "${RECOMMENDED_CODE}"
  )"

  CONFLICT_RESPONSE="${TMP_DIR}/conflict.json"

  echo
  echo "[e2e] Verify conflicting code/tag confirmation is rejected"
  echo "[e2e] code=${RECOMMENDED_CODE}"
  echo "[e2e] deliberately wrong tag=${WRONG_TAG}"

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
    echo "[e2e] actual HTTP: ${CONFLICT_CODE}"

    if [[ -s "${CONFLICT_RESPONSE}" ]]; then
      cat "${CONFLICT_RESPONSE}"
      echo
    fi

    exit 1
  fi

  echo "[e2e] HTTP 400: OK"

  # После ошибочного confirm job обязан всё ещё ждать подтверждения.
  AFTER_CONFLICT_RESPONSE="${TMP_DIR}/after-conflict-status.json"

  AFTER_CONFLICT_CODE="$(
    post_form \
      "${AFTER_CONFLICT_RESPONSE}" \
      -F "action=status" \
      -F "request_id=${REQUEST_ID}"
  )"

  require_success \
    "${AFTER_CONFLICT_CODE}" \
    "${AFTER_CONFLICT_RESPONSE}" \
    "status after conflicting confirm"

  AFTER_CONFLICT_STATUS="$(
    json_field \
      "${AFTER_CONFLICT_RESPONSE}" \
      "status"
  )"

  if [[ "${AFTER_CONFLICT_STATUS}" != "awaiting_confirmation" ]]; then
    echo "[e2e] ERROR: invalid confirm mutated job state"
    pretty_json \
      "${AFTER_CONFLICT_RESPONSE}"
    exit 1
  fi

  echo "[e2e] Job still awaits confirmation: OK"

  # --------------------------------------------------------------------
  # CORRECT CONFIRM BY PUBLIC TAG
  # --------------------------------------------------------------------

  CONFIRM_RESPONSE="${TMP_DIR}/confirm-tag.json"

  echo
  echo "[e2e] Correct confirmation by public tag=${RECOMMENDED_TAG}"

  CONFIRM_CODE="$(
    post_form \
      "${CONFIRM_RESPONSE}" \
      -F "action=confirm" \
      -F "request_id=${REQUEST_ID}" \
      -F "checklist_tag=${RECOMMENDED_TAG}"
  )"

  require_success \
    "${CONFIRM_CODE}" \
    "${CONFIRM_RESPONSE}" \
    "confirm by tag"

  pretty_json \
    "${CONFIRM_RESPONSE}"

  CONFIRMED_CODE="$(
    json_field \
      "${CONFIRM_RESPONSE}" \
      "checklist_code"
  )"

  CONFIRMED_TAG="$(
    json_field \
      "${CONFIRM_RESPONSE}" \
      "checklist_tag"
  )"

  if [[ "${CONFIRMED_CODE}" != "${RECOMMENDED_CODE}" ]]; then
    echo "[e2e] ERROR: confirmation returned wrong code"
    exit 1
  fi

  if [[ "${CONFIRMED_TAG}" != "${RECOMMENDED_TAG}" ]]; then
    echo "[e2e] ERROR: confirmation returned wrong tag"
    exit 1
  fi

  # --------------------------------------------------------------------
  # IDEMPOTENT CONFIRM BY INTERNAL CODE
  # --------------------------------------------------------------------

  REPEAT_CONFIRM_RESPONSE="${TMP_DIR}/confirm-code-repeat.json"

  echo
  echo "[e2e] Repeat confirmation by internal code"
  echo "[e2e] This must not create a duplicate logical job"

  REPEAT_CONFIRM_CODE="$(
    post_form \
      "${REPEAT_CONFIRM_RESPONSE}" \
      -F "action=confirm" \
      -F "request_id=${REQUEST_ID}" \
      -F "checklist_code=${RECOMMENDED_CODE}"
  )"

  require_success \
    "${REPEAT_CONFIRM_CODE}" \
    "${REPEAT_CONFIRM_RESPONSE}" \
    "repeated confirm by code"

  pretty_json \
    "${REPEAT_CONFIRM_RESPONSE}"

  REPEAT_STATUS="$(
    json_field \
      "${REPEAT_CONFIRM_RESPONSE}" \
      "status"
  )"

  case "${REPEAT_STATUS}" in
    queued|processing|completed)
      echo "[e2e] Idempotent repeated confirmation accepted: OK"
      ;;
    *)
      echo "[e2e] ERROR: unexpected repeat-confirm status: ${REPEAT_STATUS}"
      exit 1
      ;;
  esac
fi

# ======================================================================
# STATUS POLLING
# ======================================================================

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

  STATUS_TAG="$(
    json_field \
      "${STATUS_RESPONSE}" \
      "checklist_tag"
  )"

  echo "[e2e] status=${JOB_STATUS} progress=${PROGRESS}% tag=${STATUS_TAG}"

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

    queued|processing)
      ;;

    awaiting_confirmation)
      echo "[e2e] ERROR: job unexpectedly returned to confirmation state"
      exit 1
      ;;

    *)
      echo "[e2e] ERROR: unexpected job status: ${JOB_STATUS}"
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

  sleep "${POLL_SECONDS}"
done

# ======================================================================
# PRIVACY BEFORE RESULT DELIVERY
# ======================================================================

echo
echo "[e2e] Verify completed backend state before delivery"

if docker compose exec -T api \
  sh -lc \
  "test ! -e '/data/jobs/${REQUEST_ID}/input.pdf' \
   && test ! -e '/data/jobs/${REQUEST_ID}/source_filename.txt' \
   && test -f '/data/jobs/${REQUEST_ID}/result.json'"
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

# ======================================================================
# RESULT
# ======================================================================

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

  cat "${RESULT_FILE}" \
    2>/dev/null \
    || true

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

  cat "${RESULT_HEADERS}"

  exit 1
fi

# ======================================================================
# RESULT JSON CONTRACT
# ======================================================================

echo
echo "[e2e] Validate JSON contract"

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
    result_path,
    expected_request_id,
    expected_code,
    expected_tag,
    expected_filename,
) = sys.argv[1:]

with open(
    result_path,
    "r",
    encoding="utf-8",
) as stream:
    payload = json.load(
        stream
    )

if not isinstance(
    payload,
    dict,
):
    raise SystemExit(
        "result root must be an object"
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

missing_metadata = (
    required_metadata
    - set(
        metadata
    )
)

if missing_metadata:
    raise SystemExit(
        "missing metadata fields: "
        + ", ".join(
            sorted(
                missing_metadata
            )
        )
    )

if metadata["request_id"] != expected_request_id:
    raise SystemExit(
        "request_id mismatch"
    )

if metadata["checklist_code"] != expected_code:
    raise SystemExit(
        "checklist_code mismatch: "
        f'{metadata["checklist_code"]!r}'
    )

if metadata["checklist_tag"] != expected_tag:
    raise SystemExit(
        "checklist_tag mismatch: "
        f'{metadata["checklist_tag"]!r}'
    )

if metadata["source_filename"] != expected_filename:
    raise SystemExit(
        "source_filename mismatch: "
        f'{metadata["source_filename"]!r} '
        f"!= {expected_filename!r}"
    )

if not isinstance(
    metadata["checklist_type"],
    str,
) or not metadata[
    "checklist_type"
].strip():
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

    if not isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        raise SystemExit(
            f"{field} must be numeric"
        )

    if value < 0:
        raise SystemExit(
            f"{field} cannot be negative"
        )

if (
    metadata["search_seconds"]
    > metadata["processing_seconds"] + 0.01
):
    raise SystemExit(
        "search_seconds cannot exceed processing_seconds"
    )

completed_at = (
    str(
        metadata[
            "completed_at"
        ]
    )
    .replace(
        "Z",
        "+00:00",
    )
)

datetime.fromisoformat(
    completed_at
)

question_count = metadata[
    "question_count"
]

if not isinstance(
    question_count,
    int,
) or question_count <= 0:
    raise SystemExit(
        "question_count must be a positive integer"
    )

if len(
    questions
) != question_count:
    raise SystemExit(
        "question_count does not match questions length"
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

    if not isinstance(
        number,
        str,
    ) or not number.strip():
        raise SystemExit(
            f"question #{index}: invalid number"
        )

    if not isinstance(
        question,
        str,
    ) or not question.strip():
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
    f'({metadata["checklist_code"]})',
)

print(
    "[e2e] checklist type:",
    metadata["checklist_type"],
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

print()
print(
    "[e2e] First non-empty answers:"
)

shown = 0

for item in questions:
    if not item["answer"].strip():
        continue

    print(
        f'  {item["number"]}. '
        f'{item["question"]}'
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
echo "[e2e] Client-side JSON copy:"
echo "${RESULT_FILE}"

echo "[e2e] Result size:"
du -h \
  "${RESULT_FILE}"

# ======================================================================
# ONE-TIME DELIVERY
# ======================================================================

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

echo "[e2e] Second result returned HTTP 404: OK"

# ======================================================================
# BACKEND FILESYSTEM AFTER DELIVERY
# ======================================================================

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

# ======================================================================
# BACKEND METADATA AFTER DELIVERY
# ======================================================================

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

echo
echo "============================================================"
echo "[e2e] REAL JSON E2E PASSED"
echo "[e2e] mode: ${MODE}"
echo "[e2e] request_id: ${REQUEST_ID}"
echo "[e2e] checklist: ${CHECKLIST_TAG_CANONICAL} (${CHECKLIST_CODE})"
echo "[e2e] client result: ${RESULT_FILE}"
echo "[e2e] backend input/result/metadata: deleted"
echo "============================================================"