#!/usr/bin/env bash
# Deploy de produção do Sistema de Monitoramento (docker-compose.prod.yml).
#
# Idempotente: garante os arquivos de config que ficam FORA do repo (.env.prod e
# infra/go2rtc.local.yaml), criando-os a partir dos respectivos .example quando
# faltam — isso evita o go2rtc entrar em crash-loop por causa do bind-mount de um
# arquivo inexistente. Depois sobe a stack.
#
# Uso:
#   ./deploy.sh            # cria configs faltantes (e para, p/ você preencher) ou sobe a stack
#   ./deploy.sh --build    # força rebuild das imagens
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE_FILE="docker-compose.prod.yml"
BUILD_FLAG="--build"
[[ "${1:-}" == "--no-build" ]] && BUILD_FLAG=""

missing_config=0

ensure_from_example() {
  local target="$1" example="$2"
  if [[ ! -f "$target" ]]; then
    if [[ -f "$example" ]]; then
      cp "$example" "$target"
      echo "[deploy] criado '$target' a partir de '$example' — PREENCHA antes de produção."
      missing_config=1
    else
      echo "[deploy] ERRO: faltam '$target' e '$example'." >&2
      exit 1
    fi
  fi
}

ensure_from_example ".env.prod" ".env.prod.example"
ensure_from_example "infra/go2rtc.local.yaml" "infra/go2rtc.local.yaml.example"

if [[ "$missing_config" == "1" ]]; then
  cat <<'MSG'

[deploy] Configs criados a partir dos exemplos. Edite ANTES de seguir:
  - .env.prod               -> segredos (DB, JWT, R2, Resend), NEXT_PUBLIC_API_URL,
                               GO2RTC_PUBLIC_URL (IP desta VPS)
  - infra/go2rtc.yaml       -> webrtc candidates: IP desta VPS:8555
  - infra/go2rtc.local.yaml -> stream recortado por câmera dual-lens
                               (preencha depois de cadastrar a câmera na UI)

Depois rode ./deploy.sh de novo.
MSG
  exit 0
fi

echo "[deploy] subindo a stack ($COMPOSE_FILE)..."
docker compose -f "$COMPOSE_FILE" up -d $BUILD_FLAG
echo "[deploy] status:"
docker compose -f "$COMPOSE_FILE" ps
