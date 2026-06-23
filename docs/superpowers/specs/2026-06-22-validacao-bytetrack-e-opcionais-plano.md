# Plano: validacao-bytetrack-e-opcionais

Nome para chamar amanhã: **validacao-bytetrack-e-opcionais**
(diga: "vamos executar o plano validacao-bytetrack-e-opcionais")

Data de criação: 2026-06-22

## 1. Validar o ByteTrack (com tráfego de dia) e decidir se vira padrão
- ByteTrack já está ATIVO em produção (Redis `tracker:backend=bytetrack`). Sem
  erros na sanidade noturna; tráfego noturno baixo demais p/ A/B.
- Amanhã, com movimento normal:
  - Comparar fragmentação: `eventos` vs `count(distinct track_id)` por janela,
    ByteTrack vs baseline legacy (legacy estava 1:1).
  - Verificar visualmente no feed ao vivo: veículo parado NÃO é recontado quando
    outro passa (R1); todos os que passam recebem OCR (R2).
  - Conferir cadência de rajada (burst-on-motion) no capture-runner.
  - DECISÃO: manter ByteTrack como padrão (mudar `TRACKER_BACKEND_DEFAULT`) OU
    reverter p/ legacy (`redis-cli set tracker:backend legacy`).

## 2. Opcionais (um por vez, cada um com brainstorm→spec→impl)
Ordem recomendada (melhor custo/benefício primeiro):
1. **Faces globais em motores de nuvem** — estende o alerta global (client_id
   NULL) para os motores de face na nuvem (AWS/Luxand/Face++). Contido, não mexe
   no gargalo de CPU. RECOMENDADO COMEÇAR POR AQUI.
2. **Animais nível 2 (YOLOv8m / SAHI)** — melhora animais/objetos pequenos, mas
   ALTO custo de CPU (backend é CPU-only). Avaliar perf antes.
3. **Re-ID / entre-câmeras** — o mais pesado (embeddings de aparência +
   associação cross-câmera + índice). Ideal com GPU. Último.

## Estado atual relevante (para retomar)
- HEAD prod ao criar o plano: `39dc300` (+ OpenALPR sendo implementado nesta sessão).
- ByteTrack: opt-in, padrão legacy no código; ATIVO via Redis em prod.
- OCR motores: fast_alpr (local, ativo), plate_recognizer (pago), OpenALPR (novo).
- Deploy: VPS git `~/monitoramento-git`, `git pull --ff-only && ./deploy.sh --build`.
