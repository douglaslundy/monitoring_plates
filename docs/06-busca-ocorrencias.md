# ETAPA 6 — Busca de ocorrências e alertas

> Pré-requisito: Etapa 5 concluída. Cole este prompt no Claude Code.

PLACAS MONITORADAS (/api/monitored-plates — isolamento por client_id):
GET / | POST / {plate, description, alert_email} | PUT /{id} | DELETE /{id}

OCORRÊNCIAS (/api/occurrences — isolamento via câmeras do cliente):
GET / params: plate (parcial), camera_id, date_from, date_to, page, limit
POST /search body {plate, date_from?, date_to?, camera_ids?} — busca parcial LIKE %plate%
Resposta: {items, total, page, pages}. Cada item: id, plate, confidence, detected_at, image_url, camera{id,name,location}
GET /stats → total_today, total_week, top_cameras, top_plates, by_hour (24h)
GET /export → CSV com filtros

FRONTEND — Busca (admin e cliente — mesma estrutura, backend filtra):
Filtros: placa, câmera (dropdown), período (date picker). Botão buscar.
Resultado: contador, exportar CSV, lista de cards:
  Thumbnail clicável, placa em badge grande, barra de confiança colorida,
  câmera e local, data/hora formatada.
Modal ao clicar: foto maior, dados completos, links para "ver mais dessa placa/câmera".

ALERTAS CLIENTE (src/app/client/alerts/page.tsx):
Cards: placa, descrição, email, toggle ativo/inativo, último alerta.
Modal "Monitorar nova placa": {placa, descrição, email}

DASHBOARD CLIENTE (src/app/client/page.tsx):
Cards métricas. Feed últimas 10 ocorrências via WebSocket. Gráfico barras 24h.

WEBSOCKET FRONTEND:
src/lib/websocket.ts: classe com reconexão automática, evento 'plate_alert'
Hook: useWebSocket(clientId) → {lastAlert, isConnected}
src/components/AlertBanner.tsx: banner no topo, auto-fecha 8s, empilha múltiplos

TESTES:
- Placa monitorada → detectada → alerta tela e email
- Busca parcial "ABC" retorna ABC1234 e ABC5678
- CSV com filtros corretos
- Cliente só vê próprias ocorrências
Execute: pytest backend/tests/ -v

## ✅ Checklist
- [ ] Busca por placa completa e parcial funciona
- [ ] Alerta aparece na tela ao detectar placa monitorada
- [ ] E-mail enviado
- [ ] Exportação CSV funciona
- [ ] WebSocket mantém conexão
