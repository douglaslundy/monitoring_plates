#!/usr/bin/env bash
# Deploy de produção do Sistema de Monitoramento (docker-compose.prod.yml).
#
# Idempotente: garante os arquivos de config que ficam FORA do repo (.env.prod e
# infra/go2rtc.local.yaml), criando-os a partir dos respectivos .example quando
# faltam. Depois sobe a stack.
#
# Uso:
#   ./deploy.sh            # cria configs faltantes ou sobe a stack
#   ./deploy.sh --build    # força rebuild das imagens
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE_FILE="docker-compose.prod.yml"
BUILD_FLAG="--build"
[[ "${1:-}" == "--no-build" ]] && BUILD_FLAG=""

missing_config=0

set_env_value() {
  local key="$1" value="$2"
  if grep -qE "^${key}=" ".env.prod"; then
    sed -i "s|^${key}=.*|${key}=${value}|" ".env.prod"
  else
    printf '%s=%s\n' "$key" "$value" >> ".env.prod"
  fi
}

resolve_compose_project() {
  if docker volume inspect monitoramento-git_postgres_data >/dev/null 2>&1 || docker ps -a --format '{{.Names}}' | grep -q '^monitoramento-git-'; then
    echo "monitoramento-git"
    return
  fi
  if docker volume inspect monitoramento_postgres_data >/dev/null 2>&1 || docker ps -a --format '{{.Names}}' | grep -q '^monitoramento-'; then
    echo "monitoramento"
    return
  fi
  echo "monitoramento-git"
}

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

  set_env_value "SECRET_KEY" "$secret_key"
  set_env_value "STORAGE_TYPE" "local"
  set_env_value "STORAGE_PATH" "./storage"
  set_env_value "NEXT_PUBLIC_API_URL" "http://192.168.0.115"
  set_env_value "CORS_ORIGINS" "http://192.168.0.115"
  set_env_value "GO2RTC_PUBLIC_URL" "http://192.168.0.115:1984"

  echo "[deploy] .env.prod criado com defaults locais para esta VPS. Revise os segredos quando quiser."
fi

if ! grep -qE '^COMPOSE_PROJECT_NAME=' ".env.prod"; then
  set_env_value "COMPOSE_PROJECT_NAME" "$(resolve_compose_project)"
fi

if grep -qE '^STORAGE_TYPE=s3$' ".env.prod" && grep -q 'SEU_ACCOUNT_ID' ".env.prod"; then
  set_env_value "STORAGE_TYPE" "local"
  set_env_value "STORAGE_PATH" "./storage"
fi

echo "[deploy] subindo a stack ($COMPOSE_FILE)..."
docker compose --env-file .env.prod -f "$COMPOSE_FILE" up -d --force-recreate --remove-orphans $BUILD_FLAG
echo "[deploy] status:"
docker compose --env-file .env.prod -f "$COMPOSE_FILE" ps
