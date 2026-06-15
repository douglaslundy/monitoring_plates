from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VehicleDetection:
    vehicle_type: str
    confidence: float
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    crop_bytes: bytes


class VehicleDetector:
    """Heuristic detector optimized for fixed traffic cameras.

    The first version intentionally stays lightweight so it can run on CPU-only
    VPS nodes. It looks for large moving-like objects in the lower half of the
    frame and classifies them by shape/area.
    """

    def detect(self, image_bytes: bytes) -> list[VehicleDetection]:
        image = self._decode_image(image_bytes)
        if image is None:
            return []

        try:
            import cv2
        except ImportError:
            cv2 = None

        if cv2 is None:
            return self._detect_without_cv2(image)

        h, w = image.shape[:2]
        roi_y = max(0, int(h * 0.30))
        roi = image[roi_y:, :]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 140)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates: list[VehicleDetection] = []
        min_area = max(1200, int(w * h * 0.01))
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area:
                continue

            x, y, box_w, box_h = cv2.boundingRect(contour)
            if box_w < 40 or box_h < 25:
                continue

            aspect_ratio = box_w / max(box_h, 1)
            if aspect_ratio < 0.5 or aspect_ratio > 8.0:
                continue

            global_y = y + roi_y
            padded = self._pad_box(x, global_y, box_w, box_h, w, h)
            crop = image[padded[1] : padded[1] + padded[3], padded[0] : padded[0] + padded[2]]
            crop_bytes = self._encode_jpeg(crop)
            if crop_bytes is None:
                continue

            vehicle_type, confidence = self._classify(area, aspect_ratio, padded[2], padded[3], w, h)
            candidates.append(
                VehicleDetection(
                    vehicle_type=vehicle_type,
                    confidence=confidence,
                    bbox_x=padded[0],
                    bbox_y=padded[1],
                    bbox_w=padded[2],
                    bbox_h=padded[3],
                    crop_bytes=crop_bytes,
                )
            )

        candidates.sort(key=lambda item: self._score_detection(item, w, h), reverse=True)
        return candidates[:3]

    def best_detection(self, image_bytes: bytes) -> Optional[VehicleDetection]:
        detections = self.detect(image_bytes)
        if not detections:
            return None
        return detections[0]

    def _decode_image(self, image_bytes: bytes):
        try:
            import cv2
            import numpy as np
        except ImportError:
            cv2 = None
            np = None

        if cv2 is not None and np is not None:
            arr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if image is None:
                return None

            h, w = image.shape[:2]
            if w > 1280:
                scale = 1280 / w
                image = cv2.resize(image, (1280, int(h * scale)))
            return image

        try:
            from PIL import Image, ImageOps
            import numpy as np
        except ImportError:
            return None

        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception:
            return None

        if image.width > 1280:
            scale = 1280 / image.width
            image = image.resize((1280, int(image.height * scale)))

        image = ImageOps.autocontrast(image)
        return np.array(image)

    def _detect_without_cv2(self, image) -> list[VehicleDetection]:
        import numpy as np

        if image.ndim == 3 and image.shape[2] >= 3:
            gray = (0.299 * image[:, :, 2] + 0.587 * image[:, :, 1] + 0.114 * image[:, :, 0]).astype(np.uint8)
        else:
            gray = image.astype(np.uint8)

        h, w = gray.shape[:2]
        roi_y = max(0, int(h * 0.30))
        roi = gray[roi_y:, :]
        small = roi[::4, ::4]
        if small.size == 0:
            return []

        threshold = int(np.clip(np.percentile(small, 38), 70, 190))
        mask = small < threshold
        components = self._connected_components(mask)
        candidates: list[VehicleDetection] = []
        min_pixels = max(18, int(mask.size * 0.001))

        for comp in components:
            if comp["pixels"] < min_pixels:
                continue

            x1 = max(0, comp["x1"] * 4)
            y1 = max(0, roi_y + comp["y1"] * 4)
            x2 = min(w, (comp["x2"] + 1) * 4)
            y2 = min(h, roi_y + (comp["y2"] + 1) * 4)
            box_w = max(1, x2 - x1)
            box_h = max(1, y2 - y1)
            if box_w < 35 or box_h < 25:
                continue

            aspect_ratio = box_w / max(box_h, 1)
            if aspect_ratio < 0.5 or aspect_ratio > 8.0:
                continue

            crop = image[y1:y2, x1:x2]
            crop_bytes = self._encode_jpeg(crop)
            if crop_bytes is None:
                continue

            area = float(box_w * box_h)
            vehicle_type, confidence = self._classify(area, aspect_ratio, box_w, box_h, w, h)
            candidates.append(
                VehicleDetection(
                    vehicle_type=vehicle_type,
                    confidence=confidence,
                    bbox_x=x1,
                    bbox_y=y1,
                    bbox_w=box_w,
                    bbox_h=box_h,
                    crop_bytes=crop_bytes,
                )
            )

        candidates.sort(key=lambda item: self._score_detection(item, w, h), reverse=True)
        return candidates[:3]

    def _encode_jpeg(self, image) -> bytes | None:
        try:
            import cv2
        except ImportError:
            cv2 = None

        if cv2 is None:
            try:
                from PIL import Image
            except ImportError:
                return None

            buffer = BytesIO()
            Image.fromarray(image).save(buffer, format="JPEG", quality=85)
            return buffer.getvalue()

        ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buf.tobytes() if ok else None

    def _pad_box(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        max_w: int,
        max_h: int,
        pad_x: float = 0.12,
        pad_y: float = 0.18,
    ) -> tuple[int, int, int, int]:
        px = max(8, int(w * pad_x))
        py = max(8, int(h * pad_y))
        x1 = max(0, x - px)
        y1 = max(0, y - py)
        x2 = min(max_w, x + w + px)
        y2 = min(max_h, y + h + py)
        return x1, y1, max(1, x2 - x1), max(1, y2 - y1)

    def _score_detection(self, detection: VehicleDetection, frame_w: int, frame_h: int) -> float:
        area_ratio = (detection.bbox_w * detection.bbox_h) / max(frame_w * frame_h, 1)
        center_x = (detection.bbox_x + detection.bbox_w / 2) / max(frame_w, 1)
        center_y = (detection.bbox_y + detection.bbox_h / 2) / max(frame_h, 1)

        center_bonus = 1.0 - min(1.0, abs(center_x - 0.5) * 1.4 + abs(center_y - 0.78) * 1.1)
        size_bonus = 1.0 - min(1.0, abs(area_ratio - 0.035) / 0.08)
        return (detection.confidence * 0.5) + (center_bonus * 0.3) + (size_bonus * 0.2)

    def _connected_components(self, mask) -> list[dict[str, int]]:
        import numpy as np

        height, width = mask.shape[:2]
        visited = np.zeros_like(mask, dtype=bool)
        components: list[dict[str, int]] = []

        for y in range(height):
            for x in range(width):
                if not mask[y, x] or visited[y, x]:
                    continue

                stack = [(y, x)]
                visited[y, x] = True
                pixels = 0
                min_x = max_x = x
                min_y = max_y = y

                while stack:
                    cy, cx = stack.pop()
                    pixels += 1
                    if cx < min_x:
                        min_x = cx
                    if cx > max_x:
                        max_x = cx
                    if cy < min_y:
                        min_y = cy
                    if cy > max_y:
                        max_y = cy

                    for ny, nx in (
                        (cy - 1, cx),
                        (cy + 1, cx),
                        (cy, cx - 1),
                        (cy, cx + 1),
                    ):
                        if ny < 0 or ny >= height or nx < 0 or nx >= width:
                            continue
                        if visited[ny, nx] or not mask[ny, nx]:
                            continue
                        visited[ny, nx] = True
                        stack.append((ny, nx))

                components.append(
                    {
                        "pixels": pixels,
                        "x1": min_x,
                        "x2": max_x,
                        "y1": min_y,
                        "y2": max_y,
                    }
                )

        components.sort(key=lambda item: item["pixels"], reverse=True)
        return components[:20]

    def _classify(
        self,
        area: float,
        aspect_ratio: float,
        box_w: int,
        box_h: int,
        frame_w: int,
        frame_h: int,
    ) -> tuple[str, float]:
        frame_area = float(frame_w * frame_h)
        area_ratio = area / frame_area

        # Truck is a conservative label here: prefer "car" unless the box is
        # really large in the frame. This avoids classifying a close car as a
        # truck just because it dominates the camera view.
        if area_ratio > 0.40 or box_w > frame_w * 0.68 or box_h > frame_h * 0.68:
            vehicle_type = "truck"
            confidence = min(0.95, 0.56 + area_ratio * 2.2)
        elif aspect_ratio < 1.4 and box_w < frame_w * 0.25 and box_h < frame_h * 0.25:
            vehicle_type = "motorcycle"
            confidence = min(0.93, 0.58 + (1.4 - aspect_ratio) * 0.2 + area_ratio * 5.0)
        else:
            vehicle_type = "car"
            confidence = min(0.94, 0.60 + area_ratio * 4.0 + max(0.0, min(aspect_ratio, 4.0) - 1.0) * 0.05)

        return vehicle_type, round(max(0.5, confidence), 3)


vehicle_detector = VehicleDetector()
