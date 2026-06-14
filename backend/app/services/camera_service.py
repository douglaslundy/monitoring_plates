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


def crop_roi_frame(
    frame_bytes: bytes,
    roi_x: float,
    roi_y: float,
    roi_width: float,
    roi_height: float,
) -> bytes:
    if roi_width <= 0 or roi_height <= 0:
        return frame_bytes
    if roi_x < 0 or roi_y < 0:
        return frame_bytes

    try:
        import cv2
        import numpy as np
    except ImportError:
        cv2 = None
        np = None

    if cv2 is not None and np is not None:
        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return frame_bytes

        h, w = frame.shape[:2]
        x1 = max(0, min(w, int(round(w * roi_x))))
        y1 = max(0, min(h, int(round(h * roi_y))))
        x2 = max(0, min(w, int(round(w * (roi_x + roi_width)))))
        y2 = max(0, min(h, int(round(h * (roi_y + roi_height)))))
        if x2 <= x1 or y2 <= y1:
            return frame_bytes

        cropped = frame[y1:y2, x1:x2]
        ok, buf = cv2.imencode(".jpg", cropped, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes() if ok else frame_bytes

    try:
        from PIL import Image
        from io import BytesIO
    except ImportError:
        return frame_bytes

    try:
        image = Image.open(BytesIO(frame_bytes))
    except Exception:
        return frame_bytes

    w, h = image.size
    x1 = max(0, min(w, int(round(w * roi_x))))
    y1 = max(0, min(h, int(round(h * roi_y))))
    x2 = max(0, min(w, int(round(w * (roi_x + roi_width)))))
    y2 = max(0, min(h, int(round(h * (roi_y + roi_height)))))
    if x2 <= x1 or y2 <= y1:
        return frame_bytes

    cropped = image.crop((x1, y1, x2, y2))
    buffer = BytesIO()
    cropped.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()
