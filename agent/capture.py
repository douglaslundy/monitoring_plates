import re
import cv2
import numpy as np
from typing import Optional, Tuple

_reader = None


def get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["pt", "en"], gpu=False)
    return _reader


_PLATE_RE = re.compile(r"^[A-Z]{3}[0-9]{4}$|^[A-Z]{3}[0-9][A-Z][0-9]{2}$")


def _normalize(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def capture_and_read(source) -> Optional[Tuple[str, float, bytes, str]]:
    """Return (plate, confidence, jpeg_bytes, raw_text) or None."""
    cap = cv2.VideoCapture(source)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None

    reader = get_reader()
    results = reader.readtext(frame)

    best_plate = None
    best_conf = 0.0
    raw_texts = []

    for _, text, conf in results:
        raw_texts.append(text)
        norm = _normalize(text)
        if _PLATE_RE.match(norm) and conf > best_conf:
            best_plate = norm
            best_conf = conf

    if not best_plate:
        return None

    _, buf = cv2.imencode(".jpg", frame)
    return best_plate, best_conf, buf.tobytes(), " | ".join(raw_texts)
