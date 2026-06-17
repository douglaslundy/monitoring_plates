"""Painel de recursos do host (CPU/RAM/disco)."""
import sys
import types
from unittest.mock import patch

from app.core.security import create_access_token


def _auth_header(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id), 'role': user.role})}"}


def _fake_psutil():
    mod = types.ModuleType("psutil")
    mod.virtual_memory = lambda: types.SimpleNamespace(
        total=8 * 1024 ** 3, used=3 * 1024 ** 3, available=5 * 1024 ** 3, percent=37.5
    )
    mod.disk_usage = lambda path: types.SimpleNamespace(
        total=100 * 1024 ** 3, used=40 * 1024 ** 3, free=60 * 1024 ** 3, percent=40.0
    )
    mod.cpu_percent = lambda interval=None: 12.5
    mod.cpu_count = lambda: 12
    return mod


def test_get_system_metrics_mapeia():
    from app.services import system_metrics_service

    with patch.dict(sys.modules, {"psutil": _fake_psutil()}):
        m = system_metrics_service.get_system_metrics()

    assert m.available is True
    assert m.cpu_count == 12
    assert m.cpu_percent == 12.5
    assert m.mem_total_mb == 8192
    assert m.mem_percent == 37.5
    assert m.disk_total_gb == 100.0
    assert m.disk_percent == 40.0


def test_get_system_metrics_degrada_sem_psutil():
    from app.services import system_metrics_service

    with patch.dict(sys.modules, {"psutil": None}):
        m = system_metrics_service.get_system_metrics()

    assert m.available is False
    assert m.cpu_count == 0


def test_system_endpoint_super_admin(client, super_admin_user):
    r = client.get("/api/ops/system", headers=_auth_header(super_admin_user))
    assert r.status_code == 200
    body = r.json()
    for key in ("cpu_percent", "cpu_count", "mem_total_mb", "mem_percent", "disk_total_gb", "disk_percent"):
        assert key in body


def test_system_endpoint_403_para_nao_admin(client, user_a):
    r = client.get("/api/ops/system", headers=_auth_header(user_a))
    assert r.status_code == 403
