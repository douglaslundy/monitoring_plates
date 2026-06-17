"""Exporta os modelos YOLO para ONNX no build (Tarefa A).

Lista em YOLO_MODELS (separados por espaço). Pesos .pt presentes no contexto
(yolov8n/s) são usados offline; os demais (ex.: yolov8m) o ultralytics baixa
(o build tem internet). Falha em um modelo NÃO interrompe os outros — o que não
exportar simplesmente fica indisponível (o detector cai no padrão disponível).
"""
import os

from ultralytics import YOLO

models = os.environ.get("YOLO_MODELS", "yolov8n yolov8s yolov8m").split()
for name in models:
    try:
        YOLO(f"{name}.pt").export(format="onnx", imgsz=640, opset=12, simplify=True)
        print(f"[export] OK {name}.onnx")
    except Exception as exc:  # noqa: BLE001
        print(f"[export] FAIL {name}: {exc}")
