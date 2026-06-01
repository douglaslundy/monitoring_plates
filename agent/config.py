import json
import os
import sys


def _load() -> dict:
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
    path = os.path.join(base, "config.json")
    if not os.path.exists(path):
        print(f"[config] config.json não encontrado em: {path}")
        print("[config] Crie o arquivo config.json na mesma pasta do agent.exe com:")
        print('  {"server_url": "http://SEU_SERVIDOR:8000", "token": "TOKEN_DA_CAMERA"}')
        input("\nPressione Enter para fechar...")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for field in ("server_url", "token"):
        if not cfg.get(field):
            print(f"[config] Campo obrigatório ausente no config.json: {field}")
            input("\nPressione Enter para fechar...")
            sys.exit(1)
    return cfg


_cfg = _load()

def _parse_camera_source(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        v = value.strip()
        if v.isdigit():
            return int(v)
        return v
    return value


AGENT_TOKEN: str = _cfg["token"]
API_URL: str = _cfg["server_url"].rstrip("/")
CAMERA_SOURCE = _parse_camera_source(_cfg.get("camera_rtsp", 0))
FRAME_INTERVAL: int = max(1, int(_cfg.get("frame_interval", 1)))
MIN_CONFIDENCE: float = float(_cfg.get("min_confidence", 0.70))
DEDUP_SECONDS: int = int(_cfg.get("dedup_seconds", 30))
