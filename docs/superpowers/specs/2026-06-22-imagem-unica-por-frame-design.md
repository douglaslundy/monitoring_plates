# Imagem única por frame, com bbox só nos objetos NOVOS

Data: 2026-06-22
Status: aprovado

## Problema
Hoje cada objeto registrado gera a própria imagem (1 frame por objeto). 3 carros
numa cena → 3 imagens quase iguais → poluição de arquivos. Além disso, objeto
parado já registrado não deve reaparecer com bbox nos frames seguintes.

## Decisão (brainstorming)
Manter a CONTAGEM por objeto (3 carros = 3 registros em Detecções/Placas e nas
estatísticas), mas os registros criados no MESMO frame **compartilham 1 imagem**,
com bounding box **apenas nos objetos NOVOS daquele frame**. Objeto parado/já
registrado não recebe bbox.

## Comportamento
1. Por frame processado, monta-se o conjunto de det. que geram registro NESTE
   frame: `newly` (novas contagens + class_change) ∪ veículos que tiveram
   ocorrência criada (1ª leitura de placa) neste frame.
2. Desenha-se UMA imagem do frame com bbox só nesses índices. Rótulo: placa
   (veículo lido, caixa amarela destacada) ou classe (pessoa/animal/veículo sem
   placa).
3. Todos os registros criados no frame (VehicleEvent + Occurrence) apontam para
   essa imagem única.
4. Objeto parado não está no conjunto → sem bbox. Quando um NOVO objeto entra,
   nova imagem com bbox só nele (vale p/ detecções e placas).

## Implementação (frame_processor + detection_overlay_service)
- `draw_detections(..., annotations: dict[int, {label, highlight}])`: desenha SÓ
  os índices anotados, com rótulo/realce por índice. (Mantém params antigos p/
  faces, que seguem desenhando todas as caixas.)
- `process_frame`:
  - 1ª leitura de placa → cria Occurrence com `image_path` provisório; **adia o
    alerta** (process_alerts) para depois da imagem final.
  - Refino de placa → mantém imagem SÓ do veículo refinado (inline, sem alerta).
  - Loop de eventos cria VehicleEvent com `image_path` provisório.
  - Ao fim: monta `annotations` (índices novos + placas), desenha/salva UMA imagem,
    atribui a todos os registros do frame, e então dispara os alertas das novas
    ocorrências.
- Faces (FaceDetection): fora do escopo (outro fluxo/tela).

## Não-objetivos
- Colapsar contagem (1 registro por cena) — explicitamente recusado: contagem
  continua por objeto.
- Mexer no reconhecimento facial.

## Testes
- 3 veículos novos no mesmo frame → 3 registros, TODOS com o mesmo `image_path`.
- Veículo parado (já contado) + novo veículo → só o novo é registrado/boxeado.
- R1/R2 anteriores seguem válidos. Suíte completa verde (processo único).
