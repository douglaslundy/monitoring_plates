"""Captura de frames RTSP/webcam (sem OCR — o backend faz detecção e leitura).

Mantém a conexão aberta e lê sempre o frame mais recente (buffer=1), evitando o
handshake RTSP por frame da versão antiga.
"""
import cv2


def open_capture(source):
    """Abre a câmera. Retorna o VideoCapture aberto ou None."""
    cap = cv2.VideoCapture(source)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    if not cap.isOpened():
        cap.release()
        return None
    return cap


def read_jpeg(cap, quality: int = 80):
    """Lê o frame mais recente e devolve JPEG em bytes (ou None se falhar)."""
    cap.grab()  # descarta o frame em buffer p/ baixa latência
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else None
