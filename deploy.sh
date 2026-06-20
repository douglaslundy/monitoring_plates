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
  secret_key="$(python3 -c "import secrets; print(secrets.token_hex(32))")"

  set_env_value() {
    local key="$1" value="$2"
    if grep -qE "^${key}=" ".env.prod"; then
      sed -i "s|^${key}=.*|${key}=${value}|" ".env.prod"
    else
      printf '%s=%s\n' "$key" "$value" >> ".env.prod"
    fi
  }

  set_env_value "SECRET_KEY" "$secret_key"
  set_env_value "STORAGE_TYPE" "local"
  set_env_value "STORAGE_PATH" "./storage"
  set_env_value "NEXT_PUBLIC_API_URL" "http://192.168.0.115"
  set_env_value "CORS_ORIGINS" "http://192.168.0.115"
  set_env_value "GO2RTC_PUBLIC_URL" "http://192.168.0.115:1984"

  echo "[deploy] .env.prod criado com defaults locais para esta VPS. Revise os segredos quando quiser."
fi

echo "[deploy] subindo a stack ($COMPOSE_FILE)..."
# Exporta vars do .env.prod para o shell antes de chamar docker compose,
# evitando que o bloco `environment:` do compose sobrescreva o `env_file`
# com strings vazias quando as variáveis não estão na shell.
set -a
# shellcheck source=.env.prod
source .env.prod
set +a
docker compose -f "$COMPOSE_FILE" up -d $BUILD_FLAG
echo "[deploy] status:"
docker compose -f "$COMPOSE_FILE" ps
