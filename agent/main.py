"""
Agent — software leve instalado no cliente.
Captura frames via RTSP e envia ao backend para processamento OCR.
"""
import time

import cv2

from config import CAMERA_SOURCE, FRAME_INTERVAL
from uploader import heartbeat, send_frame

_HEARTBEAT_INTERVAL = 30


def capture_jpeg(source) -> bytes | None:
    cap = cv2.VideoCapture(source)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes()


def main() -> None:
    print("[agent] iniciando...")
    last_heartbeat = 0.0

    while True:
        now = time.time()

        if now - last_heartbeat >= _HEARTBEAT_INTERVAL:
            ok = heartbeat()
            print(f"[agent] heartbeat: {'ok' if ok else 'falhou — tentará novamente'}")
            last_heartbeat = now

        try:
            jpeg = capture_jpeg(CAMERA_SOURCE)
            if jpeg:
                ok = send_frame(jpeg)
                print(f"[agent] frame enviado: {'ok' if ok else 'falhou'}")
            else:
                print("[agent] falha ao capturar frame — verifique a câmera")
        except Exception as e:
            print(f"[agent] erro inesperado: {e}")

        time.sleep(FRAME_INTERVAL)


if __name__ == "__main__":
    main()
