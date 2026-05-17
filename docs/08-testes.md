# ETAPA 8 — Testes completos

> Pré-requisito: Etapa 7 concluída. Cole este prompt no Claude Code.

CONFIGURAÇÃO (backend/tests/conftest.py):
Fixtures: db_session (SQLite memória, rollback por teste), test_plans, super_admin_user,
client_a, client_b, admin_a, user_a, camera_rtsp_a, camera_agent_a, camera_b,
http_super_admin, http_admin_a, http_user_a (AsyncClient autenticados)

TESTES DE AUTENTICAÇÃO (test_auth.py):
login correto retorna token | senha errada 401 | usuário inativo 401
sem token 401 | super_admin com token client 403 | token expirado 401

ISOLAMENTO MULTI-TENANT (test_isolation.py):
admin_a não vê câmeras/usuários/ocorrências do client_b
busca de placa retorna só do próprio cliente
agent_token de camera_b rejeitado pelo client_a

CÂMERAS (test_cameras.py):
super_admin cria câmera para qualquer cliente
client não cria câmera para outro cliente
camera_agent gera token único
/api/agent/frame token correto 200 | token errado 401
endpoint enfileira task Celery (mock Celery)

OCR (test_ocr.py) com imagens sintéticas Pillow:
"ABC1234" detecta | "ABC1D23" detecta | imagem branca None
"ABCDE12" None | confiança baixa descartada | duplicata 30s ignorada

OCORRÊNCIAS (test_occurrences.py):
busca exata e parcial | filtro data | paginação | CSV | cliente só vê próprias

ALERTAS (test_alerts.py) com mock email e WebSocket:
placa monitorada detectada dispara alerta
email enviado se plano permite | não enviado se não permite
WebSocket disparado | sem duplicata para mesma occurrence

EXECUTAR:
pytest backend/tests/ -v --cov=app --cov-report=html --cov-report=term

Meta: 80% cobertura mínima.
Se falhar: mostre erro completo, corrija o código, rode novamente.
Ao final: testes passados/falhados, cobertura por módulo.

## ✅ Checklist
- [ ] 0 failures
- [ ] Cobertura acima de 80%
- [ ] Isolamento multi-tenant validado
- [ ] Testes OCR passam
