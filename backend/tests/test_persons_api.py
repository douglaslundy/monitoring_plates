from io import BytesIO
from unittest.mock import patch

from app.core.security import create_access_token
from app.models.person import Person
from app.models.user import User, UserRole


def _auth(user: User) -> dict:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_person(client, admin_a):
    headers = _auth(admin_a)
    r = client.post("/api/persons", json={"name": "Maria", "cpf": "11122233344"}, headers=headers)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    r2 = client.get("/api/persons", headers=headers)
    assert r2.status_code == 200
    assert any(p["id"] == pid for p in r2.json())


def test_person_tenant_isolation(client, db, admin_a, client_b):
    other = Person(client_id=client_b.id, name="De Outro Cliente")
    db.add(other)
    db.commit()
    db.refresh(other)
    r = client.get(f"/api/persons/{other.id}", headers=_auth(admin_a))
    assert r.status_code in (403, 404)


def test_client_user_cannot_create(client, db, user_a):
    r = client.post("/api/persons", json={"name": "X"}, headers=_auth(user_a))
    assert r.status_code == 403


def test_upload_face_calls_enroll(client, db, admin_a):
    from app.services.face_service import EnrollResult

    pid = client.post("/api/persons", json={"name": "Joao"}, headers=_auth(admin_a)).json()["id"]

    with (
        patch("app.api.routes.persons.save_bytes", return_value="persons/x/face.jpg"),
        patch(
            "app.api.routes.persons.face_recognizer.enroll",
            return_value=EnrollResult(engine_type="opencv", embedding=[0.1, 0.2], external_ref=None),
        ) as mock_enroll,
    ):
        r = client.post(
            f"/api/persons/{pid}/face",
            files={"file": ("face.jpg", BytesIO(b"imgbytes"), "image/jpeg")},
            headers=_auth(admin_a),
        )
    assert r.status_code == 200, r.text
    assert mock_enroll.call_count == 1
    assert r.json()["faces_count"] == 1
    assert r.json()["photo_url"] is not None
