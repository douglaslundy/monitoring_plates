"""
Agent - software leve instalado no cliente.

Mantém a câmera RTSP aberta e envia frames JPEG ao backend, que faz a detecção
de veículos e a leitura de placas (ANPR). O agente NÃO roda OCR localmente — é
só um "pusher" de frames, usado quando a VPS não alcança a câmera diretamente.
"""
import time

from capture import open_capture, read_jpeg
from config import CAMERA_SOURCE, FRAME_INTERVAL
from uploader import heartbeat, send_frame

_HEARTBEAT_INTERVAL = 30
_RECONNECT_SECONDS = 5


def main() -> None:
    print("[agent] iniciando...")
    last_heartbeat = 0.0
    cap = None

    while True:
        now = time.time()

        if now - last_heartbeat >= _HEARTBEAT_INTERVAL:
            ok = heartbeat()
            print(f"[agent] heartbeat: {'ok' if ok else 'falhou - tentara novamente'}")
            last_heartbeat = now

        if cap is None:
            cap = open_capture(CAMERA_SOURCE)
            if cap is None:
                print("[agent] falha ao conectar a camera - nova tentativa em breve")
                time.sleep(_RECONNECT_SECONDS)
                continue
            print("[agent] camera conectada")

        try:
            jpeg = read_jpeg(cap)
        except Exception as e:
            print(f"[agent] erro de leitura: {e}")
            jpeg = None

        if jpeg is None:
            print("[agent] leitura falhou - reconectando")
            cap.release()
            cap = None
            time.sleep(_RECONNECT_SECONDS)
            continue

        ok = send_frame(jpeg)
        if not ok:
            print("[agent] envio de frame falhou")

        time.sleep(FRAME_INTERVAL)


if __name__ == "__main__":
    main()
