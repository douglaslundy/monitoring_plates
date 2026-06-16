# ─── Stage 1: export YOLOv8n → ONNX (ultralytics/torch usados só no build) ───
# O runtime NÃO leva PyTorch: só copiamos o .onnx resultante.
FROM python:3.11-slim AS model-export
ENV YOLO_OFFLINE=True
RUN pip install --no-cache-dir ultralytics==8.3.0 onnx==1.17.0 onnxslim
# ultralytics importa cv2 (opencv) → precisa de libGL/glib no sistema.
# (depois do pip p/ preservar o cache da camada pesada do pip/torch)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /export
# Pesos enviados no repo (a VPS não baixa do github) → export 100% local.
COPY yolov8n.pt /export/yolov8n.pt
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx', imgsz=640, opset=12, simplify=True)" \
    && test -f yolov8n.onnx

# ─── Stage 2: runtime leve (onnxruntime + fast-alpr, sem torch/easyocr) ───
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    MODELS_DIR=/app/models

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Modelo de detecção de veículos (YOLOv8n) gerado no estágio anterior.
COPY --from=model-export /export/yolov8n.onnx /app/models/yolov8n.onnx

# Pré-baixa os modelos do fast-alpr durante o build (build tem internet) para
# que o container rode 100% OFFLINE na VPS. O cache fica embutido na imagem.
RUN python -c "from fast_alpr import ALPR; ALPR()" || echo "[build] aviso: warm do fast-alpr falhou (sera baixado no 1o uso)"

COPY . .

EXPOSE 8000
