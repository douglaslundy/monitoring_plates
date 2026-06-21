from datetime import date
from app.models.person import Person
from app.models.person_face import PersonFace


def test_create_person_with_face(db, client_a):
    p = Person(client_id=client_a.id, name="Joao Silva", cpf="12345678900",
               birth_date=date(1990, 5, 1), phone="11999998888", address="Rua A, 10",
               alert_active=True, alert_email="a@b.com")
    db.add(p)
    db.commit()
    db.refresh(p)
    face = PersonFace(person_id=p.id, engine_type="opencv", embedding=[0.1, 0.2], image_path="x.jpg")
    db.add(face)
    db.commit()
    assert p.is_active is True
    assert p.faces[0].engine_type == "opencv"
