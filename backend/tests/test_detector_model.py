"""Tarefa A: seleção do modelo de detecção (YOLO)."""
from app.core.security import create_access_token
from app.services import detector_model_service as dms
from app.api.routes import detector as detector_route


def _auth_header(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id), 'role': user.role})}"}


def _make_models(tmp_path, names):
    for n in names:
        (tmp_path / f"{n}.onnx").write_text("x")
    (tmp_path / "ruido.txt").write_text("x")


def test_available_models_lista_onnx(tmp_path, monkeypatch):
    _make_models(tmp_path, ["yolov8n", "yolov8s"])
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    assert dms.available_models() == ["yolov8n", "yolov8s"]


def test_default_prefere_m(tmp_path, monkeypatch):
    _make_models(tmp_path, ["yolov8n", "yolov8s", "yolov8m"])
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    assert dms.default_model() == "yolov8m"


def test_default_cai_para_s_sem_m(tmp_path, monkeypatch):
    _make_models(tmp_path, ["yolov8n", "yolov8s"])
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    assert dms.default_model() == "yolov8s"


def test_get_selected_usa_redis_valido(tmp_path, monkeypatch):
    _make_models(tmp_path, ["yolov8s", "yolov8m"])
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))

    class FakeC:
        def get(self, k):
            return "yolov8s"

    monkeypatch.setattr(dms, "_client", lambda: FakeC())
    assert dms.get_selected_model() == "yolov8s"


def test_get_selected_ignora_redis_invalido(tmp_path, monkeypatch):
    _make_models(tmp_path, ["yolov8s", "yolov8m"])
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))

    class FakeC:
        def get(self, k):
            return "yolov8x"  # nao disponivel

    monkeypatch.setattr(dms, "_client", lambda: FakeC())
    assert dms.get_selected_model() == "yolov8m"  # cai no padrao


def test_set_rejeita_modelo_indisponivel(tmp_path, monkeypatch):
    _make_models(tmp_path, ["yolov8s"])
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    assert dms.set_selected_model("yolov8x") is False


def test_set_aceita_modelo_disponivel(tmp_path, monkeypatch):
    _make_models(tmp_path, ["yolov8s", "yolov8m"])
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    saved = {}

    class FakeC:
        def set(self, k, v):
            saved[k] = v

    monkeypatch.setattr(dms, "_client", lambda: FakeC())
    assert dms.set_selected_model("yolov8m") is True
    assert saved.get("detector:model") == "yolov8m"


# ── Endpoint /api/detector/model ─────────────────────────────────────────────


def test_get_model_endpoint(client, super_admin_user, monkeypatch):
    monkeypatch.setattr(detector_route, "available_models", lambda: ["yolov8n", "yolov8s", "yolov8m"])
    monkeypatch.setattr(detector_route, "default_model", lambda: "yolov8m")
    monkeypatch.setattr(detector_route, "get_selected_model", lambda: "yolov8s")
    r = client.get("/api/detector/model", headers=_auth_header(super_admin_user))
    assert r.status_code == 200
    body = r.json()
    assert body["current"] == "yolov8s"
    assert body["default"] == "yolov8m"
    assert body["available"] == ["yolov8n", "yolov8s", "yolov8m"]


def test_put_model_super_admin_ok(client, super_admin_user, monkeypatch):
    monkeypatch.setattr(detector_route, "available_models", lambda: ["yolov8s", "yolov8m"])
    monkeypatch.setattr(detector_route, "default_model", lambda: "yolov8m")
    monkeypatch.setattr(detector_route, "set_selected_model", lambda name: True)
    monkeypatch.setattr(detector_route, "get_selected_model", lambda: "yolov8m")
    r = client.put("/api/detector/model", json={"model": "yolov8m"}, headers=_auth_header(super_admin_user))
    assert r.status_code == 200
    assert r.json()["current"] == "yolov8m"


def test_put_model_rejeita_invalido(client, super_admin_user, monkeypatch):
    monkeypatch.setattr(detector_route, "available_models", lambda: ["yolov8s"])
    r = client.put("/api/detector/model", json={"model": "yolov8x"}, headers=_auth_header(super_admin_user))
    assert r.status_code == 400


def test_put_model_negado_para_nao_admin(client, user_a, monkeypatch):
    monkeypatch.setattr(detector_route, "available_models", lambda: ["yolov8s", "yolov8m"])
    r = client.put("/api/detector/model", json={"model": "yolov8m"}, headers=_auth_header(user_a))
    assert r.status_code == 403
