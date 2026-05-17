import json
import os
import sys


def _load() -> dict:
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
    path = os.path.join(base, "config.json")
    if not os.path.exists(path):
        print(f"[config] config.json não encontrado em: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for field in ("server_url", "token"):
        if not cfg.get(field):
            print(f"[config] Campo obrigatório ausente no config.json: {field}")
            sys.exit(1)
    return cfg


_cfg = _load()

AGENT_TOKEN: str = _cfg["token"]
API_URL: str = _cfg["server_url"].rstrip("/")
CAMERA_SOURCE = _cfg.get("camera_rtsp", "0")
FRAME_INTERVAL: int = int(_cfg.get("frame_interval", 1))
MIN_CONFIDENCE: float = float(_cfg.get("min_confidence", 0.70))
DEDUP_SECONDS: int = int(_cfg.get("dedup_seconds", 30))
