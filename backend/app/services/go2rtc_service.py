"""Integração com o go2rtc para live em tempo real (WebRTC).

O go2rtc mantém UMA conexão RTSP por câmera e a multiplexa para o ANPR e para
os operadores via WebRTC (vídeo de baixa latência, usando o H.264 da câmera —
o FastAPI sai do caminho do vídeo). Aqui registramos/removemos câmeras no go2rtc
pela REST API dele.

Cada câmera vira um stream nomeado pelo seu UUID. O navegador acessa
`GO2RTC_PUBLIC_URL/stream.html?src=<camera_id>`.

Câmeras DUAL-LENS que compartilham o mesmo RTSP URL (ex.: dois recortes do
mesmo DVR) usam um stream "base" intermediário: go2rtc abre o RTSP uma única
vez e cada lente lê do stream base via RTSP local (evita limite de conexões
simultâneas do DVR).
"""
from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 5


def _api_base() -> str:
    return settings.GO2RTC_URL.rstrip("/")


def stream_name(camera_id: str) -> str:
    return str(camera_id)


def public_stream_url(camera_id: str) -> str:
    """URL do player WebRTC do go2rtc para o navegador do operador."""
    base = settings.GO2RTC_PUBLIC_URL.rstrip("/")
    return f"{base}/stream.html?src={stream_name(camera_id)}"


def _base_stream_id(rtsp_url: str) -> str:
    """ID estável para o stream base de um dado URL RTSP."""
    return "base_" + hashlib.sha256(rtsp_url.encode()).hexdigest()[:16]


def build_source(rtsp_url: str, dual_lens: bool = False, lens_side: str | None = None) -> str:
    """Monta a fonte (`src`) do stream para o go2rtc (câmera isolada, sem base).

    - Câmera normal: a própria URL RTSP.
    - Câmera **dual-lens**: fonte ffmpeg que referencia o template de recorte
      definido no `go2rtc.yaml` (`lens_lower` / `lens_upper`).
    """
    if dual_lens and lens_side in ("upper", "lower"):
        template = "lens_lower" if lens_side == "lower" else "lens_upper"
        return f"ffmpeg:{rtsp_url}#video={template}"
    return rtsp_url


def _build_source_via_base(base_id: str, lens_side: str) -> str:
    """Fonte para câmera dual-lens que reutiliza um stream base local do go2rtc."""
    template = "lens_lower" if lens_side == "lower" else "lens_upper"
    # Usa o RTSP interno do go2rtc — evita abrir um segundo conexão ao DVR.
    return f"ffmpeg:rtsp://127.0.0.1:8554/{base_id}#video={template}"


def _put_stream(name: str, src: str) -> bool:
    """Registra/atualiza um stream no go2rtc via REST PUT."""
    try:
        import requests
        resp = requests.put(
            f"{_api_base()}/api/streams",
            params={"name": name, "src": src},
            timeout=_TIMEOUT,
        )
        ok = resp.status_code < 400
        if not ok:
            logger.warning("go2rtc register %s -> HTTP %s (src=%s)", name, resp.status_code, src)
        return ok
    except Exception as exc:
        logger.warning("go2rtc indisponível ao registrar %s: %s", name, exc)
        return False


def _ensure_base_stream(rtsp_url: str) -> Optional[str]:
    """Garante que existe um stream base (sem crop) para o RTSP URL. Retorna o ID."""
    base_id = _base_stream_id(rtsp_url)
    _put_stream(base_id, rtsp_url)
    return base_id


def register_stream(
    camera_id: str, rtsp_url: str, dual_lens: bool = False, lens_side: str | None = None
) -> bool:
    """Cadastra/atualiza um stream no go2rtc (idempotente, câmera individual).

    Para câmeras dual-lens isoladas (sem sibling na mesma URL), usa o template
    de recorte diretamente. Para grupos, use `sync_streams` que detecta URLs
    compartilhadas e cria o stream base.
    """
    if not settings.GO2RTC_ENABLED or not rtsp_url:
        return False
    src = build_source(rtsp_url, dual_lens, lens_side)
    return _put_stream(stream_name(camera_id), src)


def remove_stream(camera_id: str) -> bool:
    if not settings.GO2RTC_ENABLED:
        return False
    try:
        import requests
        resp = requests.delete(
            f"{_api_base()}/api/streams",
            params={"src": stream_name(camera_id)},
            timeout=_TIMEOUT,
        )
        return resp.status_code < 400
    except Exception as exc:
        logger.debug("go2rtc indisponível ao remover %s: %s", camera_id, exc)
        return False


def sync_streams(db) -> int:
    """Registra no go2rtc todas as câmeras RTSP ativas.

    Câmeras que compartilham o mesmo RTSP URL (ex.: dois recortes do mesmo DVR)
    recebem um stream base intermediário para evitar múltiplas conexões ao DVR.
    Retorna quantos streams de câmera foram registrados com sucesso.
    """
    if not settings.GO2RTC_ENABLED:
        return 0
    from app.models.camera import Camera, ConnectionType

    cameras = (
        db.query(Camera)
        .filter(
            Camera.connection_type == ConnectionType.rtsp,
            Camera.is_active == True,  # noqa: E712
            Camera.rtsp_url.isnot(None),
        )
        .all()
    )

    # Agrupa câmeras por RTSP URL para detectar URLs compartilhadas.
    url_groups: dict[str, list] = defaultdict(list)
    for camera in cameras:
        url_groups[camera.rtsp_url].append(camera)

    count = 0
    for rtsp_url, group in url_groups.items():
        if len(group) > 1:
            # Múltiplas câmeras no mesmo URL (dual-lens do mesmo DVR):
            # registra um stream base para abrir a conexão RTSP uma única vez.
            base_id = _ensure_base_stream(rtsp_url)
            logger.info(
                "go2rtc: stream base '%s' para %d câmeras em %s",
                base_id, len(group), rtsp_url,
            )
            for camera in group:
                if camera.dual_lens and camera.lens_side in ("upper", "lower"):
                    src = _build_source_via_base(base_id, camera.lens_side)
                else:
                    src = f"rtsp://127.0.0.1:8554/{base_id}"
                if _put_stream(stream_name(str(camera.id)), src):
                    count += 1
        else:
            camera = group[0]
            if register_stream(
                str(camera.id), camera.rtsp_url, bool(camera.dual_lens), camera.lens_side
            ):
                count += 1

    logger.info("go2rtc: %s/%s streams sincronizados", count, len(cameras))
    return count
