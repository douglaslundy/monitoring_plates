# ETAPA 4 — Câmeras: RTSP e Agente Local

> Pré-requisito: Etapa 3 concluída. Cole este prompt no Claude Code.

ROTAS DE CÂMERAS (/api/cameras — isolamento por client_id):
GET / com status online/offline
POST / cria câmera. Para agent: gera agent_token UUID único automático.
GET /{id} com últimas 5 ocorrências | PUT /{id} | DELETE /{id}
POST /{id}/test captura frame (só RTSP) retorna base64
GET /{id}/token retorna agent_token

ROTA DO AGENTE (/api/agent/frame):
POST Header Authorization: Bearer {agent_token}
Body multipart/form-data campo 'frame' JPEG
Autentica pelo token, atualiza last_seen_at, enfileira: process_frame.delay(camera_id, frame_bytes)
Retorna {received: true, camera_id}

SERVIÇO (backend/app/services/camera_service.py):
check_rtsp_online(rtsp_url, timeout=5) → bool
capture_rtsp_frame(rtsp_url) → bytes JPEG
generate_agent_token() → UUID sem hífens

FRONTEND:
Grid de cards: nome, local, badge tipo (RTSP/Agente), ponto pulsando (online/offline), última detecção
Wizard "Nova câmera" 2 passos:
  Passo 1: escolha tipo com explicação
  Passo 2: campos. Se agent → modal com token e instruções após salvar

Modal de instruções do agente:
Token copiável. config.json pronto para copiar:
{"server_url":"http://...","token":"TOKEN","camera_rtsp":"rtsp://...","frame_interval":1}
Passo a passo: baixar agent.exe, criar config.json, executar.

AGENTE LOCAL (agent/):
main.py: loop captura → envia → aguarda → repete, reconexão automática
config.py: lê config.json, valida campos obrigatórios
capture.py: RTSP com OpenCV, JPEG qualidade 80%, retry em desconexão
uploader.py: POST multipart, retry 3x com backoff exponencial
build.sh: pyinstaller --onefile --name agent main.py
README.md: instalação para pessoa não técnica

TESTES:
- Câmera agent → token único gerado
- /api/agent/frame token correto → 200
- /api/agent/frame token errado → 401
- Cliente não vê câmeras de outro cliente
Execute: pytest backend/tests/test_cameras.py -v

## ✅ Checklist
- [ ] Câmera RTSP criada e teste retorna frame ou erro claro
- [ ] Câmera agent criada com token único
- [ ] Endpoint agente funciona com token correto, rejeita token errado
- [ ] Modal de instruções exibe token e config.json
