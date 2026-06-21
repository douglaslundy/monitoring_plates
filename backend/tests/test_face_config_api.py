from app.core.security import create_access_token
from app.models.user import User


def _auth(user: User) -> dict:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_super_admin_cria_ativa_lista(client, super_admin_user):
    headers = _auth(super_admin_user)
    r = client.post(
        "/api/face-config",
        json={"engine_type": "rekognition", "api_token": "AKIA", "api_secret": "sec", "region": "us-east-1"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    # segredos mascarados
    assert r.json()["api_token"] == "***configured***"

    r2 = client.post(f"/api/face-config/{cid}/activate", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["is_active"] is True

    r3 = client.get("/api/face-config", headers=headers)
    assert r3.status_code == 200
    assert any(c["id"] == cid for c in r3.json())


def test_opencv_test_sem_credenciais(client, super_admin_user):
    headers = _auth(super_admin_user)
    cid = client.post("/api/face-config", json={"engine_type": "opencv"}, headers=headers).json()["id"]
    r = client.post(f"/api/face-config/{cid}/test", headers=headers)
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_client_admin_barrado(client, admin_a):
    headers = _auth(admin_a)
    r = client.get("/api/face-config", headers=headers)
    assert r.status_code == 403
