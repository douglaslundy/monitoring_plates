import re
import logging
import time
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_PLATE_RE = re.compile(r"^[A-Z]{3}\d{4}$|^[A-Z]{3}\d[A-Z]\d{2}$")


class PlateRecognizer:
    def __init__(self) -> None:
        self._reader = None

    def _get_reader(self):
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(["pt"], gpu=False)
        return self._reader

    def recognize(self, image_bytes: bytes) -> Optional[dict]:
        import numpy as np
        import cv2

        t0 = time.time()

        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        # 2. Resize to max 1280px width
        h, w = img.shape[:2]
        if w > 1280:
            scale = 1280 / w
            img = cv2.resize(img, (1280, int(h * scale)))

        # 3. Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 4. CLAHE contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # 5. Find plate ROI or use full image
        roi = self._find_plate_roi(enhanced, img)

        # 6. EasyOCR
        reader = self._get_reader()
        results = reader.readtext(roi)

        # 7. Validate each result
        for _, text, confidence in results:
            normalized = re.sub(r"[^A-Z0-9]", "", text.upper())
            if _PLATE_RE.match(normalized) and confidence >= settings.AGENT_MIN_CONFIDENCE:
                elapsed = time.time() - t0
                logger.info(
                    "OCR: plate=%s conf=%.2f time=%.2fs", normalized, confidence, elapsed
                )
                return {"plate": normalized, "confidence": float(confidence), "bbox": None}

        return None

    def _find_plate_roi(self, gray, original):
        import cv2

        blurred = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Canny(blurred, 30, 200)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:30]

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if h == 0:
                continue
            ratio = w / h
            # Plate aspect ratio is roughly 3:1 to 5:1
            if 3.0 <= ratio <= 5.0 and w > 80:
                return original[y : y + h, x : x + w]

        return original


recognizer = PlateRecognizer()
