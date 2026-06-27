#!/usr/bin/env bash
# Executado na VPS a partir de um checkout Git do projeto.
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "== git pull =="
git fetch --all --prune
git checkout main
git pull --ff-only origin main

echo "== bootstrap/deploy =="
bash ./deploy.sh --build

echo "== restart go2rtc (carrega templates lens_lower/lens_upper do go2rtc.yaml) =="
docker compose --env-file .env.prod -f docker-compose.prod.yml restart go2rtc

echo "== ps =="
docker compose --env-file .env.prod -f docker-compose.prod.yml ps

echo "== migracao atual (deve ser head) =="
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T backend alembic current || true

echo "== health backend (dentro do container) =="
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T backend curl -s -o /dev/null -w 'health=%{http_code}\n' http://localhost:8000/health || true

echo "== streams go2rtc =="
sleep 4
curl -s http://localhost:1984/api/streams || true
echo

echo "== DEPLOY OK =="
