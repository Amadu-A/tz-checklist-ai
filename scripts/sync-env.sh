#!/usr/bin/env bash
# scripts/sync-env.sh

set -Eeuo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  pwd
)"

cd "${ROOT_DIR}"

EXAMPLE_FILE="${1:-.env.example}"
ENV_FILE="${2:-.env}"

if [[ ! -s "${EXAMPLE_FILE}" ]]; then
  echo "[env-sync] ERROR: ${EXAMPLE_FILE} is missing or empty"
  exit 1
fi

if [[ ! -e "${ENV_FILE}" ]]; then
  cp "${EXAMPLE_FILE}" "${ENV_FILE}"
  echo "[env-sync] Created ${ENV_FILE} from ${EXAMPLE_FILE}"
  exit 0
fi

if [[ ! -s "${ENV_FILE}" ]]; then
  echo "[env-sync] ERROR: ${ENV_FILE} exists but is empty"
  echo "[env-sync] Refusing to overwrite it automatically"
  exit 1
fi

BACKUP="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "${ENV_FILE}" "${BACKUP}"

echo "[env-sync] Backup: ${BACKUP}"

ADDED=0

while IFS= read -r line || [[ -n "${line}" ]]; do
  line="${line%$'\r'}"

  case "${line}" in
    ''|\#*)
      continue
      ;;
  esac

  key="${line%%=*}"

  if [[ ! "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "[env-sync] ERROR: invalid key in ${EXAMPLE_FILE}: ${key}"
    cp "${BACKUP}" "${ENV_FILE}"
    exit 1
  fi

  if ! grep -q "^${key}=" "${ENV_FILE}"; then
    printf '%s\n' "${line}" >> "${ENV_FILE}"
    echo "[env-sync] Added: ${key}"
    ADDED=$((ADDED + 1))
  fi
done < "${EXAMPLE_FILE}"

echo "[env-sync] Added variables: ${ADDED}"
echo "[env-sync] Existing values and secrets were preserved"