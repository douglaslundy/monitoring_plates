"""
Etapa 8 — Testes de ocorrências: busca, filtros, paginação e exportação.
"""

import csv
import io
import pytest
from datetime import datetime, timezone, timedelta

from app.core.security import create_access_token
from app.models.occurrence import Occurrence
from app.models.user import User


def _tok(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {_tok(user)}"}


def _occ(db, camera, plate: str, delta_minutes: int = 0) -> Occurrence:
    occ = Occurrence(
        camera_id=camera.id,
        plate=plate,
        confidence=0.95,
        image_path="cameras/x/img.jpg",
        detected_at=datetime.now(timezone.utc) - timedelta(minutes=delta_minutes),
    )
    db.add(occ)
    db.commit()
    db.refresh(occ)
    return occ


# ── Busca por placa ───────────────────────────────────────────────────────────

def test_busca_placa_parcial(client, db, user_a, camera_rtsp_a):
    """Partial plate search returns matching records."""
    _occ(db, camera_rtsp_a, "ABC1234")
    _occ(db, camera_rtsp_a, "ABC5678")
    _occ(db, camera_rtsp_a, "XYZ9W87")

    res = client.post(
        "/api/occurrences/search",
        json={"plate": "ABC"},
        headers=_auth(user_a),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    plates = {i["plate"] for i in data["items"]}
    assert plates == {"ABC1234", "ABC5678"}


def test_busca_placa_exata(client, db, user_a, camera_rtsp_a):
    """Exact plate search returns only that plate."""
    _occ(db, camera_rtsp_a, "ABC1234")
    _occ(db, camera_rtsp_a, "ABC5678")

    res = client.post(
        "/api/occurrences/search",
        json={"plate": "ABC1234"},
        headers=_auth(user_a),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["plate"] == "ABC1234"


def test_busca_sem_filtro_retorna_tudo(client, db, user_a, camera_rtsp_a):
    """Empty plate filter returns all records."""
    for plate in ["ABC1234", "DEF5678", "GHI9J01"]:
        _occ(db, camera_rtsp_a, plate)

    res = client.post(
        "/api/occurrences/search",
        json={"plate": ""},
        headers=_auth(user_a),
    )
    assert res.status_code == 200
    assert res.json()["total"] == 3


# ── Filtros de data ───────────────────────────────────────────────────────────

def test_busca_com_filtro_date_from(client, db, user_a, camera_rtsp_a):
    """date_from filter excludes older occurrences."""
    now = datetime.now(timezone.utc)
    _occ(db, camera_rtsp_a, "OLD1234", delta_minutes=120)  # 2h ago
    _occ(db, camera_rtsp_a, "NEW1234", delta_minutes=10)   # 10 min ago

    date_from = (now - timedelta(minutes=30)).isoformat()

    res = client.post(
        "/api/occurrences/search",
        json={"plate": "", "date_from": date_from},
        headers=_auth(user_a),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["plate"] == "NEW1234"


def test_busca_com_filtro_date_to(client, db, user_a, camera_rtsp_a):
    """date_to filter excludes newer occurrences."""
    now = datetime.now(timezone.utc)
    _occ(db, camera_rtsp_a, "OLD1234", delta_minutes=120)  # 2h ago
    _occ(db, camera_rtsp_a, "NEW1234", delta_minutes=10)   # 10 min ago

    date_to = (now - timedelta(minutes=30)).isoformat()

    res = client.post(
        "/api/occurrences/search",
        json={"plate": "", "date_to": date_to},
        headers=_auth(user_a),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["plate"] == "OLD1234"


# ── Paginação ─────────────────────────────────────────────────────────────────

def test_paginacao_primeira_pagina(client, db, user_a, camera_rtsp_a):
    """page=1 limit=2 returns first 2 of 5 records."""
    for i in range(5):
        _occ(db, camera_rtsp_a, f"AAA{i:04d}", delta_minutes=i)

    res = client.post(
        "/api/occurrences/search",
        json={"plate": "", "page": 1, "limit": 2},
        headers=_auth(user_a),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 5
    assert data["pages"] == 3
    assert len(data["items"]) == 2


def test_paginacao_segunda_pagina(client, db, user_a, camera_rtsp_a):
    """page=2 limit=2 returns 2 records from the middle."""
    for i in range(5):
        _occ(db, camera_rtsp_a, f"AAA{i:04d}", delta_minutes=i)

    res = client.post(
        "/api/occurrences/search",
        json={"plate": "", "page": 2, "limit": 2},
        headers=_auth(user_a),
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 2


# ── GET por ID ────────────────────────────────────────────────────────────────

def test_get_occurrence_proprio_cliente(client, db, user_a, camera_rtsp_a):
    """user_a can GET an occurrence from their own client's camera."""
    occ = _occ(db, camera_rtsp_a, "ABC1234")
    res = client.get(f"/api/occurrences/{occ.id}", headers=_auth(user_a))
    assert res.status_code == 200
    assert res.json()["plate"] == "ABC1234"


def test_get_occurrence_nao_encontrada_404(client, db, user_a):
    """GET a nonexistent occurrence ID returns 404."""
    import uuid
    fake_id = uuid.uuid4()
    res = client.get(f"/api/occurrences/{fake_id}", headers=_auth(user_a))
    assert res.status_code == 404


# ── GET list endpoint ─────────────────────────────────────────────────────────

def test_list_occurrences_endpoint(client, db, user_a, camera_rtsp_a):
    """GET /api/occurrences/ list endpoint returns paginated results."""
    _occ(db, camera_rtsp_a, "ABC1234")
    _occ(db, camera_rtsp_a, "DEF5678")

    res = client.get("/api/occurrences/", headers=_auth(user_a))
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert "items" in data
    assert "pages" in data


def test_list_occurrences_com_filtro_placa(client, db, user_a, camera_rtsp_a):
    """GET /api/occurrences/?plate=ABC filters results."""
    _occ(db, camera_rtsp_a, "ABC1234")
    _occ(db, camera_rtsp_a, "XYZ9W87")

    res = client.get("/api/occurrences/?plate=ABC", headers=_auth(user_a))
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["plate"] == "ABC1234"


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_stats_retorna_totais_corretos(client, db, user_a, camera_rtsp_a):
    """Stats endpoint returns correct today/week counts."""
    _occ(db, camera_rtsp_a, "ABC1234")
    _occ(db, camera_rtsp_a, "DEF5678")

    res = client.get("/api/occurrences/stats", headers=_auth(user_a))
    assert res.status_code == 200
    data = res.json()
    assert data["total_today"] == 2
    assert data["total_week"] == 2
    assert len(data["by_hour"]) == 24


# ── CSV export ────────────────────────────────────────────────────────────────

def test_csv_export_com_filtro_placa(client, db, user_a, camera_rtsp_a):
    """CSV export with plate filter returns only matching rows."""
    _occ(db, camera_rtsp_a, "ABC1234")
    _occ(db, camera_rtsp_a, "XYZ9W87")

    res = client.get("/api/occurrences/export?plate=ABC", headers=_auth(user_a))
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]

    reader = csv.DictReader(io.StringIO(res.text))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["Placa"] == "ABC1234"


def test_csv_export_com_filtro_data(client, db, user_a, camera_rtsp_a):
    """CSV export with date_from filter excludes older records."""
    now = datetime.now(timezone.utc)
    _occ(db, camera_rtsp_a, "OLD1234", delta_minutes=120)
    _occ(db, camera_rtsp_a, "NEW5678", delta_minutes=5)

    date_from = (now - timedelta(minutes=30)).isoformat()
    res = client.get(
        "/api/occurrences/export",
        params={"date_from": date_from},
        headers=_auth(user_a),
    )
    assert res.status_code == 200
    reader = csv.DictReader(io.StringIO(res.text))
    rows = list(reader)
    plates = {r["Placa"] for r in rows}
    assert "NEW5678" in plates
    assert "OLD1234" not in plates
