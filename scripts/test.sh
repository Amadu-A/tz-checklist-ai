#!/usr/bin/env bash
# scripts/test.sh

set -Eeuo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  pwd
)"

cd "${ROOT_DIR}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[tests] Created .env from .env.example"
fi

mkdir -p \
  "${ROOT_DIR}/tests/fixtures/private"

echo "[tests] Validate Docker Compose"
docker compose config --quiet

echo "[tests] Build test image"
docker compose build api

echo "[tests] Ruff + full pytest suite"

docker compose run \
  --rm \
  --no-deps \
  -v "${ROOT_DIR}/tests/fixtures/private:/test-data:ro" \
  api \
  sh -lc '
    ruff check app tests &&
    pytest -q
  '

echo "[tests] ALL TESTS PASSED"