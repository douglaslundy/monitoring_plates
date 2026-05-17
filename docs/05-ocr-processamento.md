# ETAPA 5 — Motor OCR e processamento de frames

> Pré-requisito: Etapa 4 concluída. Cole este prompt no Claude Code.
> ATENÇÃO: EasyOCR baixa modelos na primeira execução (~500MB). Aguarde.

SERVIÇO OCR (backend/app/services/ocr_service.py):
class PlateRecognizer com inicialização lazy:
  reader = easyocr.Reader(['pt'], gpu=False)

  def recognize(self, image_bytes) → dict | None:
    {plate, confidence, bbox} ou None

    Pipeline:
    1. Decodificar bytes → numpy array OpenCV
    2. Redimensionar para largura máxima 1280px
    3. Escala de cinza
    4. CLAHE para contraste
    5. Detectar região da placa: bilateral → Canny → contornos → retângulos proporção 3:1 a 5:1
       Se encontrar → recortar para OCR. Se não → imagem completa.
    6. easyocr.readtext()
    7. Para cada resultado: limpar (só alfanuméricos, maiúsculas), validar:
       r'^[A-Z]{3}\d{4}$' (antigo) ou r'^[A-Z]{3}\d[A-Z]\d{2}$' (Mercosul)
       Se válido e confidence > AGENT_MIN_CONFIDENCE → retornar
    8. Nenhum válido → None. Log: tempo, placa, confidence.

WORKER (backend/app/workers/frame_processor.py):
@celery_app.task(name='process_frame', queue='frames')
def process_frame(camera_id, frame_bytes):
  1. Buscar câmera e plano do cliente
  2. recognize(frame_bytes)
  3. None ou confidence baixa → retornar
  4. Verificar duplicata: mesma câmera + placa nos últimos AGENT_DEDUP_SECONDS
  5. Calcular expires_at conforme retention_days do plano
  6. storage_service.save(frame_bytes, camera_id)
  7. Criar Occurrence no banco
  8. Verificar monitored_plates → alert_service.trigger_alert()

ALERTAS (backend/app/services/alert_service.py):
def trigger_alert(occurrence, monitored_plate):
  Verificar se já enviado para esta occurrence
  Se alert_email e plano permite → email_service.send_plate_alert()
  Se realtime_alerts → websocket_manager.broadcast_to_client()
  Salvar AlertSent no banco

E-MAIL (backend/app/services/email_service.py) usando biblioteca resend:
def send_plate_alert(to_email, plate, camera_name, location, detected_at, image_url):
  Assunto: "⚠️ Placa {plate} detectada — {camera_name}"
  HTML: placa, câmera, local, data/hora, imagem, link sistema

WEBSOCKET (backend/app/websocket/manager.py):
class ConnectionManager: connections dict[client_id, list[WebSocket]]
  connect / disconnect / broadcast_to_client
Rota: GET /api/ws/{client_id}?token={jwt} — valida token, ping 30s
Payload: {type:"plate_alert", occurrence_id, plate, camera_name, location, detected_at, image_url, confidence}

STORAGE (backend/app/services/storage_service.py):
save(image_bytes, camera_id) → path: YYYY/MM/DD/{uuid}.jpg
get_url(path) → URL
Suporte: local (padrão) e s3 via STORAGE_TYPE
Rota GET /api/images/{path:path}: serve com verificação de acesso

RETENÇÃO (backend/app/workers/retention_cleaner.py):
Celery Beat às 02:00: busca expires_at < agora → deleta arquivo + registro

TESTES (backend/tests/test_ocr.py) com imagens sintéticas Pillow:
  "ABC1234" em fundo branco → detecta
  "ABC1D23" → detecta
  Imagem branca → None
  "ABCDE12" → None
  Duplicata em 30s → ignorada
  Pipeline completo → occurrence no banco
Execute e mostre taxa de acerto e tempo médio.

## ✅ Checklist
- [ ] OCR detecta placa em imagem sintética
- [ ] Formato inválido retorna None
- [ ] Duplicata em 30s ignorada
- [ ] Occurrence salva com imagem no disco
- [ ] WebSocket conecta e recebe mensagem de teste
