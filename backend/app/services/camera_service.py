import uuid
from typing import Optional


def generate_agent_token() -> str:
    """Return a 32-char hex UUID (no hyphens) for agent authentication."""
    return uuid.uuid4().hex


def check_rtsp_online(rtsp_url: str, timeout: int = 5) -> bool:
    import cv2
    cap = cv2.VideoCapture(rtsp_url)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
    opened = cap.isOpened()
    cap.release()
    return opened


def capture_rtsp_frame(rtsp_url: str) -> Optional[bytes]:
    import cv2
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes()


def capture_frame(stream_url: str) -> Optional[bytes]:
    return capture_rtsp_frame(stream_url)


def crop_half_frame(frame_bytes: bytes, side: str) -> bytes:
    import cv2
    import numpy as np

    arr = np.frombuffer(frame_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return frame_bytes

    h = frame.shape[0]
    mid = h // 2
    if side == "lower":
        cropped = frame[mid:, :]
    else:
        cropped = frame[:mid, :]

    ok, buf = cv2.imencode(".jpg", cropped, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes() if ok else frame_bytes
