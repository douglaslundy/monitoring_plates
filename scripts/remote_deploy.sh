#!/usr/bin/env bash
# Executado NA VPS pelo deploy_to_vps.ps1 (via plink). Mantido como arquivo
# proprio para evitar mangling de aspas/linhas ao passar comando multi-linha
# pelo PowerShell -> plink.
set -e
cd /home/lundy/monitoramento

echo "== build/up backend+workers+frontend =="
docker compose -f docker-compose.prod.yml up -d --build backend worker retention-worker capture-runner frontend

echo "== restart go2rtc (carrega templates lens_lower/lens_upper do go2rtc.yaml) =="
docker compose -f docker-compose.prod.yml restart go2rtc

echo "== ps =="
docker compose -f docker-compose.prod.yml ps

echo "== migracao atual (deve ser head) =="
docker compose -f docker-compose.prod.yml exec -T backend alembic current || true

echo "== health backend (dentro do container) =="
docker compose -f docker-compose.prod.yml exec -T backend curl -s -o /dev/null -w 'health=%{http_code}\n' http://localhost:8000/health || true

echo "== streams go2rtc =="
sleep 4
curl -s http://localhost:1984/api/streams || true
echo

echo "== DEPLOY OK =="
