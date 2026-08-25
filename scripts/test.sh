#!/usr/bin/env bash
# scripts/test.sh

set -Eeuo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  pwd
)"

cd "${ROOT_DIR}"

# .env.example является обязательным шаблоном конфигурации.
# Пустой шаблон означает ошибку структуры проекта, поэтому
# продолжать тестирование в таком состоянии нельзя.
if [[ ! -s .env.example ]]; then
  echo "[tests] ERROR: .env.example is missing or empty"
  exit 1
fi

# -s проверяет одновременно существование файла и его размер.
# Поэтому новый проект и случайно созданный пустой .env
# автоматически получают рабочую dev-конфигурацию.
if [[ ! -s .env ]]; then
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