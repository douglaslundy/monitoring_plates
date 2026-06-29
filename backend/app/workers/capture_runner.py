"""Capture-runner: captura RTSP persistente + motion gating (CPU baixa).

Substitui o antigo `poll_rtsp_cameras` (Celery beat de 1s que reabria a conexão
RTSP a cada tick — 2s de handshake por frame). Aqui cada câmera ativa tem uma
thread que mantém a conexão aberta, lê o frame mais recente e só enfileira para
o ANPR (`process_frame`) quando há **movimento** no quadro. Em cena parada o
custo é ~zero (só um diff de imagem), então a fila não satura.

Live/preview NÃO depende mais deste módulo: o go2rtc serve o vídeo em tempo real
(WebRTC). Ainda assim salvamos um `latest.jpg` em baixa taxa para o thumbnail de
fallback do painel.

Rodar: `python -m app.workers.capture_runner`
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone

# RTSP sobre TCP é bem mais confiável que UDP (default do OpenCV/FFmpeg), que
# costuma falhar a leitura em muitas câmeras/redes. Definir ANTES de usar o cv2.
# stimeout: socket I/O timeout em microsegundos (5s) para detectar drop rápido.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000")

from app.core.config import settings

logger = logging.getLogger("capture_runner")

# Intervalo de re-sincronização da lista de câmeras com o banco.
_CAMERA_SYNC_SECONDS = 15.0
# Salva latest.jpg p/ thumbnail no máximo a cada N segundos (independe do ANPR).
_PREVIEW_SAVE_SECONDS = 1.0
# Espera entre tentativas de reconexão de uma câmera com falha.
_RECONNECT_SECONDS = 5.0


class CameraCapture(threading.Thread):
    """Thread que mantém uma câmera RTSP aberta e enfileira frames com movimento."""

    def __init__(self, camera_id: str, rtsp_url: str, dual_lens: bool, lens_side: str | None) -> None:
        super().__init__(daemon=True, name=f"capture-{camera_id[:8]}")
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.dual_lens = dual_lens
        self.lens_side = lens_side
        self._stop = threading.Event()
        self._prev_gray = None
        self._last_preview_save = 0.0
        self._last_seen_update = 0.0
        self._last_force_send = 0.0
        self._force_send = True  # 1o frame após conectar sempre dispara ANPR
        self._last_motion_at = 0.0  # p/ a rajada do backend bytetrack
        self._backend: str | None = None
        self._backend_checked_at = 0.0
        self._redis_client = None

    def _tracker_backend(self) -> str:
        """Backend de rastreamento atual (cacheado ~10s p/ não bater no Redis por frame)."""
        now = time.time()
        if self._backend is None or now - self._backend_checked_at > 10.0:
            try:
                from app.services.tracker_backend_service import get_backend

                self._backend = get_backend()
            except Exception:
                self._backend = "legacy"
            self._backend_checked_at = now
        return self._backend or "legacy"

    def stop(self) -> None:
        self._stop.set()

    # ── Loop principal ──────────────────────────────────────────────────────
    def run(self) -> None:
        import cv2

        while not self._stop.is_set():
            cap = self._open(cv2)
            if cap is None:
                time.sleep(_RECONNECT_SECONDS)
                continue

            self._force_send = True
            self._prev_gray = None
            frame_interval = 1.0 / max(0.5, settings.CAPTURE_FPS)
            fail_count = 0
            try:
                while not self._stop.is_set():
                    started = time.time()
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        # Tolera falhas transitórias antes de reconectar.
                        fail_count += 1
                        if fail_count >= 15:
                            logger.warning("Camera %s: leitura falhou %dx, reconectando", self.camera_id, fail_count)
                            break
                        time.sleep(0.2)
                        continue
                    fail_count = 0
                    self._handle_frame(cv2, frame)
                    elapsed = time.time() - started
                    if elapsed < frame_interval:
                        time.sleep(frame_interval - elapsed)
            finally:
                cap.release()

        logger.info("Camera %s: capture encerrado", self.camera_id)

    def _open(self, cv2):
        try:
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            if not cap.isOpened():
                logger.warning("Camera %s: não abriu RTSP", self.camera_id)
                cap.release()
                return None
            logger.info("Camera %s: RTSP conectada", self.camera_id)
            return cap
        except Exception as exc:
            logger.warning("Camera %s: erro ao abrir (%s)", self.camera_id, exc)
            return None

    # ── Processamento de um frame ───────────────────────────────────────────
    def _handle_frame(self, cv2, frame) -> None:
        if self.dual_lens and self.lens_side in ("upper", "lower"):
            h = frame.shape[0]
            mid = h // 2
            frame = frame[mid:, :] if self.lens_side == "lower" else frame[:mid, :]

        # Descarta frames onde a parte inferior está completamente preta —
        # sinal de decodificação H.264 incompleta (FFMPEG error concealment).
        # Esses frames causam imagens de detecção corrompidas (só o topo visível).
        if self._is_partial_frame(frame):
            return

        now = time.time()
        moved = self._has_motion(cv2, frame)

        # Thumbnail de fallback (baixa taxa, independente do ANPR).
        if now - self._last_preview_save >= _PREVIEW_SAVE_SECONDS:
            self._save_preview(cv2, frame)
            self._last_preview_save = now
            self._touch_last_seen(now)

        # Envia ao ANPR quando: há movimento (principal), é o 1º frame após
        # conectar (bootstrap), OU passou o heartbeat sem nenhum envio (rede de
        # segurança p/ algo lento/estático que o motion gating perdeu). Em cena
        # parada isso vira ~1 envio a cada CAPTURE_FORCE_SEND_SECONDS — antes era
        # a cada 8s, floodando o pipeline com o objeto estacionado.
        if moved:
            self._last_motion_at = now
        heartbeat_due = (now - self._last_force_send) >= settings.CAPTURE_FORCE_SEND_SECONDS
        # Rajada (só backend bytetrack): durante a passagem (até CAPTURE_BURST_SECONDS
        # após o último movimento) envia TODOS os frames, p/ o ByteTrack ver a
        # passagem com continuidade (IoU alto entre frames consecutivos).
        burst = (
            self._tracker_backend() == "bytetrack"
            and (now - self._last_motion_at) <= settings.CAPTURE_BURST_SECONDS
        )
        if not (moved or burst or self._force_send or heartbeat_due):
            return
        # Envio "forçado" = NÃO pode ser descartado pela amostragem de alto volume.
        # Inclui: bootstrap/heartbeat SEM movimento (mantêm vivo o track do objeto
        # PARADO) e os frames da rajada do bytetrack (precisam de continuidade).
        forced = ((not moved) and (self._force_send or heartbeat_due)) or burst
        self._force_send = False
        # Qualquer envio (movimento/bootstrap/heartbeat) reinicia o heartbeat:
        # ele só dispara após um período inteiro SEM nenhum frame enviado.
        self._last_force_send = now
        self._enqueue(cv2, frame, forced=forced)

    def _is_partial_frame(self, frame) -> bool:
        """Detecta frames literalmente corrompidos pelo FFMPEG (error concealment):
        linhas inferiores preenchidas com pixels exatamente zero. Critério rigoroso:
        pelo menos 50% das linhas do quarto inferior são completamente pretas
        (soma de canal = 0) E o topo tem conteúdo real (mean > 15). Isso evita
        descartar cenas escuras legítimas, onde sempre há algum ruído de sensor.
        """
        try:
            import numpy as np
            h = frame.shape[0]
            if h < 64:
                return False
            top_mean = float(np.mean(frame[: int(h * 0.2)].astype(np.float32)))
            # Só verifica a parte inferior se o topo tem conteúdo visível
            if top_mean < 15.0:
                return False
            bottom = frame[int(h * 0.75) :, :]
            # Conta linhas completamente pretas (soma por linha = 0)
            row_sums = bottom.sum(axis=(1, 2))
            zero_rows = int(np.sum(row_sums == 0))
            total_rows = bottom.shape[0]
            if total_rows > 0 and zero_rows / total_rows >= 0.5:
                logger.warning(
                    "Camera %s: frame parcial descartado (%d/%d linhas zeradas na base, topo mean=%.1f)",
                    self.camera_id,
                    zero_rows,
                    total_rows,
                    top_mean,
                )
                return True
        except Exception:
            pass
        return False

    def _has_motion(self, cv2, frame) -> bool:
        small = cv2.resize(frame, (320, 180))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if self._prev_gray is None:
            self._prev_gray = gray
            return False
        delta = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray
        _, thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)
        changed = int(cv2.countNonZero(thresh))
        ratio = changed / float(thresh.size)
        return ratio >= settings.MOTION_MIN_AREA_RATIO

    def _ocr_queue_depth(self) -> int:
        """Profundidade da fila OCR (frames). Usa cliente Redis cacheado."""
        try:
            import redis as _redis

            if self._redis_client is None:
                self._redis_client = _redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=0.3,
                    socket_timeout=0.3,
                )
            for q in ("frames", "celery"):
                depth = self._redis_client.llen(q)
                if depth:
                    return int(depth)
        except Exception:
            self._redis_client = None  # força reconexão na próxima vez
        return 0

    def _enqueue(self, cv2, frame, forced: bool = False) -> None:
        import base64

        # Frames não-forçados são descartados quando a fila já está profunda:
        # o worker não consegue processar rápido o suficiente (YOLO ~1s/frame) e
        # o acúmulo causa frames antigos sendo salvos (pessoa já de costas).
        if not forced:
            depth = self._ocr_queue_depth()
            if depth > settings.WORKER_DELAY_QUEUE_THRESHOLD:
                logger.debug("Camera %s: frame descartado (fila=%d)", self.camera_id, depth)
                return

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, settings.CAPTURE_JPEG_QUALITY])
        if not ok:
            return
        try:
            from app.workers.frame_processor import process_frame

            process_frame.apply_async(
                args=[self.camera_id, base64.b64encode(buf.tobytes()).decode(), forced],
                expires=10,
            )
        except Exception as exc:
            logger.warning("Camera %s: falha ao enfileirar (%s)", self.camera_id, exc)

    def _save_preview(self, cv2, frame) -> None:
        try:
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, settings.CAPTURE_JPEG_QUALITY])
            if not ok:
                return
            from app.services.storage_service import save_latest_frame
            from app.services.preview_telemetry_service import record_preview_frame

            save_latest_frame(buf.tobytes(), self.camera_id)
            record_preview_frame(self.camera_id)
        except Exception as exc:
            logger.debug("Camera %s: preview save falhou (%s)", self.camera_id, exc)

    def _touch_last_seen(self, now: float) -> None:
        if now - self._last_seen_update < 30.0:
            return
        self._last_seen_update = now
        try:
            from app.core.database import SessionLocal
            from app.models.camera import Camera

            db = SessionLocal()
            try:
                cam = db.query(Camera).filter(Camera.id == uuid.UUID(self.camera_id)).first()
                if cam:
                    cam.last_seen_at = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.debug("Camera %s: last_seen update falhou (%s)", self.camera_id, exc)


def _worker_needs_restart(worker: "CameraCapture", cfg: dict) -> bool:
    """True se a config de captura (RTSP/lente) divergir da thread em execução."""
    return (
        cfg["rtsp_url"] != worker.rtsp_url
        or bool(cfg["dual_lens"]) != bool(worker.dual_lens)
        or cfg["lens_side"] != worker.lens_side
    )


class CaptureManager:
    """Sincroniza threads de captura com as câmeras RTSP ativas do banco."""

    def __init__(self) -> None:
        self._workers: dict[str, CameraCapture] = {}
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()
        for worker in self._workers.values():
            worker.stop()

    def _active_cameras(self) -> dict[str, dict]:
        from app.core.database import SessionLocal
        from app.models.camera import Camera, ConnectionType

        db = SessionLocal()
        try:
            cameras = (
                db.query(Camera)
                .filter(
                    Camera.connection_type == ConnectionType.rtsp,
                    Camera.is_active == True,  # noqa: E712
                    Camera.rtsp_url.isnot(None),
                )
                .all()
            )
            return {
                str(c.id): {
                    "rtsp_url": c.rtsp_url,
                    "dual_lens": bool(c.dual_lens),
                    "lens_side": c.lens_side,
                }
                for c in cameras
            }
        finally:
            db.close()

    def _sync(self) -> None:
        try:
            desired = self._active_cameras()
        except Exception as exc:
            logger.warning("Falha ao listar câmeras: %s", exc)
            return

        # Encerra threads de câmeras removidas/desativadas ou cuja config de
        # captura mudou (RTSP, dual_lens ou lens_side). Sem checar a lente, trocar
        # a lente exibida não tinha efeito: o worker seguia recortando a antiga.
        for camera_id in list(self._workers.keys()):
            worker = self._workers[camera_id]
            cfg = desired.get(camera_id)
            if cfg is None or _worker_needs_restart(worker, cfg):
                worker.stop()
                del self._workers[camera_id]

        # Inicia threads novas.
        new_started = False
        for camera_id, cfg in desired.items():
            if camera_id not in self._workers:
                worker = CameraCapture(camera_id, cfg["rtsp_url"], cfg["dual_lens"], cfg["lens_side"])
                worker.start()
                self._workers[camera_id] = worker
                new_started = True

        # Resincroniza todos os streams go2rtc quando há mudanças — usa sync_streams
        # para detectar câmeras com o mesmo RTSP URL e criar stream base único,
        # evitando múltiplas conexões simultâneas ao mesmo DVR.
        if new_started:
            try:
                from app.services.go2rtc_service import sync_streams
                from app.core.database import SessionLocal
                _db = SessionLocal()
                try:
                    sync_streams(_db)
                finally:
                    _db.close()
            except Exception as exc:
                logger.debug("go2rtc sync falhou: %s", exc)

    def run(self) -> None:
        logger.info("capture-runner iniciado")
        while not self._stop.is_set():
            self._sync()
            self._stop.wait(_CAMERA_SYNC_SECONDS)
        logger.info("capture-runner encerrado")


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    manager = CaptureManager()
    try:
        manager.run()
    except KeyboardInterrupt:
        manager.stop()


if __name__ == "__main__":
    run()
