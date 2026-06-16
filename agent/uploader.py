import time
import requests
from config import AGENT_TOKEN, API_URL


def heartbeat() -> bool:
    try:
        res = requests.post(
            f"{API_URL}/api/agent/heartbeat",
            data={"agent_token": AGENT_TOKEN},
            timeout=5,
        )
        if not res.ok:
            print(f"[uploader] heartbeat falhou: {res.status_code} {res.text}")
        return res.ok
    except Exception:
        return False


def send_frame(jpeg_bytes: bytes) -> bool:
    """Send raw JPEG frame via Bearer token auth with exponential backoff retry."""
    for attempt in range(3):
        try:
            res = requests.post(
                f"{API_URL}/api/agent/frame",
                headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
                files={"frame": ("frame.jpg", jpeg_bytes, "image/jpeg")},
                timeout=10,
            )
            if not res.ok:
                print(f"[uploader] envio frame falhou: {res.status_code} {res.text}")
            return res.ok
        except Exception as e:
            if attempt == 2:
                print(f"[uploader] erro após 3 tentativas: {e}")
                return False
            time.sleep(2 ** attempt)
    return False
