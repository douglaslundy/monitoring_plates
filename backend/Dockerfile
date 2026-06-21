# ─── Stage 1: export YOLOv8 (n/s/m/l/x) → ONNX (ultralytics/torch só no build) ───
# O runtime NÃO leva PyTorch: só copiamos os .onnx resultantes. O admin escolhe
# em runtime qual modelo usar (yolov8n/s/m/l/x) — todos são embutidos aqui.
FROM python:3.11-slim AS model-export
# Modelos a exportar. n/s vêm dos .pt no repo (offline); m/l/x são baixados no build.
ARG YOLO_MODELS="yolov8n yolov8s yolov8m yolov8l yolov8x"
ENV YOLO_MODELS=${YOLO_MODELS}
# Torch CPU 2.4.1: usa o exportador ONNX legado (sem onnxscript) e evita ~2GB de
# wheels CUDA. Instalado antes do ultralytics p/ ele não puxar a versão CUDA.
RUN pip install --no-cache-dir torch==2.4.1 torchvision==0.19.1 \
    --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir ultralytics==8.3.0 onnx==1.17.0 onnxslim
# ultralytics importa cv2 (opencv) → precisa de libGL/glib no sistema.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /export
# Pesos enviados no repo (yolov8n/s) → export local; os demais são baixados.
COPY yolov8n.pt yolov8s.pt /export/
COPY export_models.py /export/export_models.py
RUN python export_models.py && ls -1 *.onnx

# ─── Stage 2: runtime leve (onnxruntime + fast-alpr, sem torch/easyocr) ───
FROM python:3.11-slim
ARG YOLO_MODEL=yolov8s

ENV PYTHONUNBUFFERED=1 \
    MODELS_DIR=/app/models \
    VEHICLE_MODEL_PATH=/app/models/${YOLO_MODEL}.onnx

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

# Modelos de detecção (YOLOv8 n/s/m...) gerados no estágio anterior. Todos são
# embutidos; o admin escolhe em runtime (detector_model_service). VEHICLE_MODEL_PATH
# (yolov8s) é o fallback sempre presente.
COPY --from=model-export /export/*.onnx /app/models/

# Modelos de reconhecimento facial (OpenCV Zoo: YuNet detecção + SFace embedding).
# Licença comercial OK. Baixados no build (que tem internet) para o container rodar
# OFFLINE. Fontes: mirror HuggingFace; fallback p/ o endpoint LFS do opencv_zoo
# (media.githubusercontent serve o binário do git-lfs, não o ponteiro). Não-fatal:
# se nenhum baixar, o motor de faces local fica em modo degradado até o .onnx
# existir em MODELS_DIR (o serviço trata a ausência sem quebrar).
RUN set -eux; \
    mkdir -p /app/models; \
    for spec in \
      "face_detection_yunet_2023mar.onnx|https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx|https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" \
      "face_recognition_sface_2021dec.onnx|https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx|https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx" ; do \
      name="${spec%%|*}"; rest="${spec#*|}"; url1="${rest%%|*}"; url2="${rest##*|}"; \
      ( curl -fsSL "$url1" -o "/app/models/$name" || curl -fsSL "$url2" -o "/app/models/$name" ) \
        && echo "[build] modelo de face baixado: $name" \
        || echo "[build] AVISO: nao baixou $name — motor de faces local degradado ate o arquivo existir em /app/models"; \
    done

# Pré-baixa os modelos do fast-alpr durante o build (build tem internet) para
# que o container rode 100% OFFLINE na VPS. O cache fica embutido na imagem.
RUN python -c "from fast_alpr import ALPR; ALPR()" || echo "[build] aviso: warm do fast-alpr falhou (sera baixado no 1o uso)"

COPY . .

EXPOSE 8000
