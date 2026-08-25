#!/usr/bin/env bash
# scripts/run.sh

set -Eeuo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  pwd
)"

cd "${ROOT_DIR}"

if [[ ! -s .env.example ]]; then
  echo "[run] ERROR: .env.example is missing or empty"
  exit 1
fi

if [[ ! -s .env ]]; then
  cp .env.example .env
  echo "[run] Created .env from .env.example"
fi

echo "[run] Validate Docker Compose"
docker compose config --quiet

echo "[run] Build and start"
docker compose up -d --build

echo "[run] Waiting for liveness"

for _ in $(seq 1 30); do
  if docker compose exec -T api \
    curl -fsS \
    http://localhost:8000/health/live \
    >/dev/null
  then
    break
  fi

  sleep 2
done

if ! docker compose exec -T api \
  curl -fsS \
  http://localhost:8000/health/live \
  >/dev/null
then
  echo "[run] Liveness check failed"
  docker compose logs --tail=100 api
  exit 1
fi

echo "[run] Checking readiness"

if ! docker compose exec -T api \
  curl -fsS \
  http://localhost:8000/health/ready \
  >/dev/null
then
  echo "[run] Readiness check failed"
  docker compose logs --tail=100 api
  exit 1
fi

echo "[run] Service is ready"
docker compose ps