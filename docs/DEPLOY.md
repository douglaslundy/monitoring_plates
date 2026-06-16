# Deploy numa VPS nova (zerada)

Checklist para clonar o repo e subir a stack **funcional**.

## Pré-requisitos
- Docker + Docker Compose v2
- A VPS precisa alcançar as câmeras RTSP (rede) e a internet (build baixa deps e modelos)

## Passos

```bash
git clone <repo> monitoramento && cd monitoramento

# 1) Cria os configs locais (fora do repo) a partir dos exemplos.
#    Sem isso o go2rtc entra em crash-loop (bind-mount de arquivo inexistente).
./deploy.sh            # cria .env.prod e infra/go2rtc.local.yaml e PARA

# 2) Preencha os configs:
#    - .env.prod                -> segredos (POSTGRES_PASSWORD, SECRET_KEY, R2,
#                                  RESEND), NEXT_PUBLIC_API_URL, GO2RTC_PUBLIC_URL
#                                  (use o IP desta VPS, ex.: http://SEU_IP:1984)
#    - infra/go2rtc.yaml        -> webrtc.candidates: SEU_IP:8555

# 3) Sobe a stack (build + migrações + seed do admin acontecem sozinhos).
./deploy.sh
```

Acesso inicial: `admin@sistema.com` / `Admin@123` (troque depois).

## O que é automático
- Build do modelo YOLO (`yolov8n.pt` -> `.onnx`) e download dos modelos do fast-alpr (OCR).
- `alembic upgrade head` + seed do admin no boot do backend.

## O que é manual (por design)
- **Segredos** em `.env.prod` (gitignored).
- **IP da VPS** em `infra/go2rtc.yaml` (candidate WebRTC) e `GO2RTC_PUBLIC_URL`.
- **Câmeras**: cadastradas pela UI (são dados, não código).
- **Live recortado de câmera dual-lens**: depois de cadastrar a câmera na UI,
  adicione o stream em `infra/go2rtc.local.yaml` usando o **UUID da câmera** e
  reinicie o go2rtc (`docker compose -f docker-compose.prod.yml restart go2rtc`).
  Modelo da linha está em `infra/go2rtc.local.yaml.example`. Motivo: a API do
  go2rtc recusa fontes com filtro/espaço, então o crop vai pelo config.

## Atenção ao sincronizar (re-sync)
`infra/go2rtc.local.yaml` e `.env.prod` ficam **fora do repo** (git-ignored) de
propósito. Um `scp -r` / `rsync` (sem `--delete`) do repositório não os toca. Se
usar `rsync --delete`, adicione `--exclude='.env.prod' --exclude='infra/go2rtc.local.yaml'`.
